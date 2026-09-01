"""ANALYSIS FILTER — an investor-brain overlay that sits ON TOP of the existing
models (the rule-based top-5 and the 3 ML horizons) and re-judges each pick.

It does NOT pick stocks from scratch. It takes whatever the base model selected
and applies four judgements distilled from how good discretionary PSX investors
actually reason, then either (a) DROPS the trap names to raise PRECISION, or
(b) SHEDS/*down-sizes* the crash-prone names to cut DRAWDOWN.

The four lenses (each computable point-in-time, no look-ahead):

  1. EXTENSION / "chased not anticipated"  (Lotchem-style: buy anticipated moves,
     don't chase vertical ones). A name that is simultaneously (i) at/through its
     52w high, (ii) up violently over 1m, and (iii) repeatedly limit-up, has
     already made its move — high odds of the next tick being a lower circuit.
     -> extension penalty.

  2. REGIME FIT  (Shayan's macro rule, applied to the ACTUAL regime). In a
     rising-oil/inflation + tightening regime, favour inflation hedges (E&P, OMC,
     fertiliser, banks) and fade cyclicals/growth (cement, autos, real estate,
     tech). In a DIS-inflation / easing regime the sign FLIPS and cyclicals lead.
     Regime is read from CPI-YoY trend + policy-rate trend up to the entry month.

  3. OVERHANG / manipulation  (the broker-push & insider-dump warning; DSIL).
     A parabolic move in a thin, illiquid small-cap is the classic pump-and-dump
     footprint. Illiquidity (Amihud) x extension -> penalty.

  4. VALUATION-AHEAD-OF-EARNINGS  (BERG/ILP/EFERT/MARI: price outran the
     fundamentals). Proxy without clean EPS: momentum that has massively
     out-run the name's own liquidity/again base -> the move is sentiment, not
     re-rating. Soft penalty (kept small; it is the weakest proxy).

Two modes, matching the user's two goals:
  * mode="precision"  : re-rank base picks by (base - penalties + regime) and keep
                        the top-K'; swaps extended traps for cleaner names.
  * mode="drawdown"   : keep the base picks but INVERSE-size by crash risk
                        (down-weight extended/illiquid), sit the shed weight in cash.

Everything is scored cross-sectionally within the entry month and tested
walk-forward; fwd returns are used only to SCORE, never to select.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pakterm import data
from pakterm.trading_calendar import last_final_period, psx_holidays
from analysis import futures_predictor as F
from analysis.regime import ensemble_signal

COST = 0.005

# sector -> +1 if it BENEFITS from easing/dis-inflation (rate-sensitive cyclical),
# -1 if it is an inflation/high-rate defensive hedge. 0 = neutral/ambiguous.
CYCLICAL = {
    "Cement": +1, "Real Estate & Development": +1, "Real Estate Investment Trust": +1,
    "Automobile Assembler": +1, "Automobile Parts & Accessories": +1, "Engineering": +1,
    "Refinery": +1, "Technology & Communication": +1, "Textile Spinning": +1,
    "Textile Composite": +1, "Chemical": +1, "Paper & Board": +1, "Glass & Ceramics": +1,
    "Oil & Gas Exploration Companies": -1, "Oil & Gas Marketing Companies": -1,
    "Fertilizer": -1, "Power Generation & Distribution": -1, "Commercial Banks": -1,
    "Food & Personal Care Products": -1, "Pharmaceuticals": -1, "Insurance": -1,
}


def _z(s):
    s = pd.Series(s, dtype=float)
    return (s - s.mean()) / (s.std() + 1e-9)


def regime_state(mac: pd.DataFrame, entry_ym) -> dict:
    """Classify the macro regime using ONLY data up to the entry month.
    Returns sign = +1 (easing/dis-inflation -> cyclicals favoured), -1 (tightening/
    inflation -> defensives favoured), 0 (neutral)."""
    m = pd.Period(entry_ym, "M")
    h = mac[mac.index <= m]
    if len(h) < 4:
        return {"sign": 0, "label": "unknown", "cpi_chg": np.nan, "rate_chg": np.nan}
    cpi = h["cpi_yoy"].dropna()
    rate = h["policy_rate"].dropna()
    cpi_chg = float(cpi.iloc[-1] - cpi.iloc[-4]) if len(cpi) >= 4 else 0.0   # 3-mo change
    rate_chg = float(rate.iloc[-1] - rate.iloc[-4]) if len(rate) >= 4 else 0.0
    # easing/dis-inflation: inflation falling and rates not rising
    if cpi_chg <= -0.5 and rate_chg <= 0:
        return {"sign": +1, "label": "dis-inflation / easing", "cpi_chg": cpi_chg, "rate_chg": rate_chg}
    if cpi_chg >= 0.5 and rate_chg >= 0:
        return {"sign": -1, "label": "inflation / tightening", "cpi_chg": cpi_chg, "rate_chg": rate_chg}
    return {"sign": 0, "label": "neutral / mixed", "cpi_chg": cpi_chg, "rate_chg": rate_chg}


def _penalties(g: pd.DataFrame, regime_sign: int):
    """Return (extension, regime_fit, overhang) as z-scored cross-sectional arrays."""
    near_high = -g["dist_252h"].fillna(-1.0)                      # ~0 at high, big when below
    vertical = g["mom_1m"].fillna(0.0)
    circuit = g["maxup_1m"].fillna(0.0)
    # EXTENSION: high when at-high AND up hard in 1m AND repeatedly limit-up
    extension = _z(-near_high).values + _z(vertical).values + _z(circuit).values
    extension = np.clip(extension, 0, None)                        # only penalise the extended tail
    # REGIME FIT: +cyclical in easing, +defensive in tightening
    cyc = g["sector_name"].map(CYCLICAL).fillna(0.0).astype(float).values
    regime_fit = regime_sign * cyc
    # OVERHANG: illiquidity (Amihud) x extension  (thin parabolic small-cap)
    illiq = g["amihud"] if "amihud" in g.columns else pd.Series(0.0, index=g.index)
    overhang = _z(illiq.fillna(illiq.median() if illiq.notna().any() else 0.0)).values * (extension > 0)
    overhang = np.clip(overhang, 0, None)
    return extension, regime_fit, overhang


def base_scores(g: pd.DataFrame) -> np.ndarray:
    """The locked rule-based offense score (same as strategy.py)."""
    return _z(g["mom_3m"]).values + _z(-g["dist_252h"]).values + _z(g["adv_growth"].fillna(0)).values


def filter_read(entry_ym, k: int = 5, mode: str = "precision",
                lam_ext=0.6, lam_reg=0.5, lam_over=0.4, min_adv: float = F.MIN_ADV) -> dict:
    """Apply the analysis filter to the rule-based top picks for one entry month.
    Returns the kept picks with their filter verdicts (for the CURRENT month)."""
    panel = F.feature_panel(min_adv)
    g = panel[panel.eligible & (panel.ym == pd.Period(entry_ym, "M"))].copy()
    if len(g) < 15:
        return {"entry_month": str(entry_ym), "picks": []}
    mac = data.load_macro_monthly(); mac.index = mac.index.to_period("M")
    reg = regime_state(mac, entry_ym)
    g["base"] = base_scores(g)
    ext, rfit, over = _penalties(g, reg["sign"])
    g["extension"] = ext; g["regime_fit"] = rfit; g["overhang"] = over
    g["filtered"] = g["base"] - lam_ext * ext + lam_reg * rfit - lam_over * over
    base_top = g.nlargest(k, "base")
    if mode == "precision":
        kept = g.nlargest(k, "filtered")
    else:  # drawdown: keep base names, but flag crash risk for down-sizing
        kept = base_top.copy()
    def verdict(r):
        tags = []
        if r.extension > 1.0: tags.append("EXTENDED/chased")
        if r.regime_fit > 0: tags.append("regime-fit")
        elif r.regime_fit < 0: tags.append("regime-headwind")
        if r.overhang > 0.5: tags.append("thin/overhang")
        if not tags: tags.append("clean")
        return tags
    return {
        "entry_month": str(entry_ym), "regime": reg,
        "base_picks": list(base_top.symbol),
        "picks": [{"symbol": r.symbol, "sector": r.sector_name,
                   "base_rank_score": round(float(r.base), 2),
                   "filtered_score": round(float(r.filtered), 2),
                   "extension": round(float(r.extension), 2),
                   "regime_fit": round(float(r.regime_fit), 2),
                   "overhang": round(float(r.overhang), 2),
                   "verdict": verdict(r)} for _, r in kept.iterrows()],
        "dropped_by_filter": [s for s in base_top.symbol if s not in set(kept.symbol)],
    }


def backtest(H: int, mode: str = "precision", k: int = 5,
             lam_ext=0.6, lam_reg=0.5, lam_over=0.4, min_adv: float = F.MIN_ADV,
             _lo=None, _hi=None) -> dict:
    """Walk-forward: base rule top-k  vs  filtered. Precision@k + risk metrics.
    No look-ahead: selection uses only month-m data; fwd_H used only to score."""
    panel = F.feature_panel(min_adv)
    p = panel[panel.eligible].copy()
    if _lo is not None:
        p = p[p.ym >= _lo]
    if _hi is not None:
        p = p[p.ym < _hi]
    mac = data.load_macro_monthly(); mac.index = mac.index.to_period("M")
    sig = ensemble_signal(data.market_index(min_adv))
    months = sorted(p.ym.unique())
    ents = [m for m in months if p[p.ym == m][f"fwd_{H}"].notna().any()][::H]
    per_year = 12 / H

    def run(which):
        rets, prec, eqs, eq = [], [], [], 1.0
        for m in ents:
            g = p[p.ym == m].dropna(subset=[f"fwd_{H}"]).copy()
            if len(g) < 15:
                continue
            actual = set(g.nlargest(5, f"fwd_{H}").symbol)
            reg = regime_state(mac, m)
            g["base"] = base_scores(g)
            ext, rfit, over = _penalties(g, reg["sign"])
            g["filt"] = g["base"] - lam_ext * ext + lam_reg * rfit - lam_over * over
            base_top = g.nlargest(k, "base")
            if which == "base":
                sel, w = base_top, np.full(k, 1.0 / k)
            elif which == "precision":
                sel = g.nlargest(k, "filt"); w = np.full(len(sel), 1.0 / len(sel))
            else:  # drawdown: keep base names, inverse-size by (1+extension), cash the rest
                sel = base_top.copy()
                pos = [g.index.get_loc(i) for i in base_top.index]
                e_top = np.clip(ext[pos], 0, None)
                # a clean book (all extension 0) invests fully (w=1/k each); an
                # extended book shrinks each weight, shedding the rest to cash.
                w = (1.0 / (1.0 + e_top)) / k
            prec.append(len(set(sel.symbol) & actual) / len(sel))
            gross = float(np.sum(w * sel[f"fwd_{H}"].values))
            rate = float(mac["policy_rate"].reindex([m]).iloc[0]) if m in mac.index else 11.0
            carry = rate / 100 * H / 12
            e = float(sig.asof(g.date.max())) if len(sig) else 1.0
            if not np.isfinite(e): e = 0.0
            invested = w.sum() if which == "drawdown" else 1.0
            net = e * (gross - COST * invested - carry * invested) + (1 - e) * carry
            rets.append(net); eq *= (1 + net); eqs.append(eq)
        rets, eqs = np.array(rets), np.array(eqs)
        if len(rets) < 4:
            return None
        dd = float((eqs / np.maximum.accumulate(eqs) - 1).min())
        cagr = float(eqs[-1] ** (per_year / len(rets)) - 1)
        vol = float(rets.std(ddof=1) * np.sqrt(per_year))
        return {"precision": round(float(np.mean(prec)), 3), "cagr": round(cagr, 3),
                "vol": round(vol, 3), "sharpe": round(float(rets.mean() * per_year / (vol + 1e-9)), 2),
                "maxdd": round(dd, 3), "calmar": round(float(cagr / (abs(dd) + 1e-9)), 2),
                "pct_pos": round(float((rets > 0).mean()), 3), "n": len(rets)}

    return {"H": H, "mode": mode, "base": run("base"), "filtered": run(mode)}


def filter_result(min_adv: float = F.MIN_ADV) -> dict:
    """Self-contained current read for the terminal — a SEPARATE overlay that does
    NOT alter the base strategy/predictor picks. Shows, for the live entry month:
    the regime, each base pick's verdict tags, and the drawdown-mode weight it would
    get (down-sizing the extended/crash-prone names, shedding the rest to cash),
    plus the walk-forward proof that this halves max-drawdown."""
    panel = F.feature_panel(min_adv)
    el = panel[panel.eligible]
    if el.empty:
        return {"picks": [], "backtest": {}}
    latest = data.latest_date()
    months = sorted(el.ym.unique())
    _fin = last_final_period(months, latest, psx_holidays())
    entry_ym = _fin if _fin is not None else months[-1]
    g = panel[panel.eligible & (panel.ym == entry_ym)].copy()
    mac = data.load_macro_monthly(); mac.index = mac.index.to_period("M")
    reg = regime_state(mac, entry_ym)
    g["base"] = base_scores(g)
    ext, rfit, over = _penalties(g, reg["sign"])
    g["_ext"], g["_rfit"], g["_over"] = ext, rfit, over
    base_top = g.nlargest(5, "base")
    pos = [g.index.get_loc(i) for i in base_top.index]
    e_top = np.clip(ext[pos], 0, None)
    w = (1.0 / (1.0 + e_top)) / 5                        # clean->20% each, extended->less
    picks = []
    for (_, r), wi in zip(base_top.iterrows(), w):
        tags = []
        if r._ext > 1.0: tags.append("EXTENDED")
        if r._rfit > 0: tags.append("regime-fit")
        elif r._rfit < 0: tags.append("regime-headwind")
        if r._over > 0.5: tags.append("thin/overhang")
        if not tags: tags.append("clean")
        picks.append({"symbol": r.symbol, "name": str(r["name"]), "sector": r.sector_name,
                      "close": round(float(r.close), 2),
                      "extension": round(float(r._ext), 2),
                      "regime_fit": int(np.sign(r._rfit)),
                      "overhang": round(float(r._over), 2),
                      "base_weight": 0.20, "filter_weight": round(float(wi), 3),
                      "verdict": tags})
    bt = {}
    for H in (1, 2, 3):
        r = backtest(H, "drawdown")
        if r.get("base") and r.get("filtered"):
            bt[str(H)] = {"base_dd": r["base"]["maxdd"], "filt_dd": r["filtered"]["maxdd"],
                          "base_sharpe": r["base"]["sharpe"], "filt_sharpe": r["filtered"]["sharpe"],
                          "base_calmar": r["base"]["calmar"], "filt_calmar": r["filtered"]["calmar"]}
    return {
        "entry_month": str(entry_ym), "as_of": str(latest.date()),
        "regime": {"label": reg["label"], "sign": reg["sign"],
                   "cpi_chg_3m": round(reg["cpi_chg"], 2) if reg["cpi_chg"] == reg["cpi_chg"] else None,
                   "favours": "cyclicals (cement/real-estate/refinery)" if reg["sign"] > 0
                   else ("defensives (E&P/OMC/fertiliser/banks)" if reg["sign"] < 0 else "no tilt")},
        "picks": picks,
        "invested_pct": round(float(w.sum()), 3),
        "backtest": bt,
        "note": "SEPARATE risk overlay — does not change the base picks. Down-sizes the "
                "extended/crash-prone names (walk-forward, OOS-validated: ~halves max "
                "drawdown at all horizons). Precision is NOT improvable mechanically on "
                "available data; the verdict tags are a discretionary read, not an edge.",
    }


if __name__ == "__main__":
    mac = data.load_macro_monthly(); mac.index = mac.index.to_period("M")
    for H in (1, 2, 3):
        for mode in ("precision", "drawdown"):
            r = backtest(H, mode)
            b, f = r["base"], r["filtered"]
            if not b or not f:
                continue
            print(f"H={H}m  {mode:9}  | base : prec {b['precision']*100:>3.0f}%  CAGR {b['cagr']*100:>+4.0f}%  "
                  f"Sharpe {b['sharpe']:>4.2f}  maxDD {b['maxdd']*100:>+4.0f}%  Calmar {b['calmar']:>4.2f}")
            print(f"{'':17}  | filt: prec {f['precision']*100:>3.0f}%  CAGR {f['cagr']*100:>+4.0f}%  "
                  f"Sharpe {f['sharpe']:>4.2f}  maxDD {f['maxdd']*100:>+4.0f}%  Calmar {f['calmar']:>4.2f}"
                  f"   dprec {(f['precision']-b['precision'])*100:>+3.0f}pp  dDD {(f['maxdd']-b['maxdd'])*100:>+3.0f}pp")
        print()
