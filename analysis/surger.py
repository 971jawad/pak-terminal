"""SURGER PREDICTOR — forward 6-month surger picks from a rule+ML+AI ensemble.

A SEPARATE, additive predictor. It does not change any existing model or panel.

Design (all validated walk-forward / OOS earlier):
  * Horizon 6 months — the horizon where surger selection actually has OOS signal
    (~27% precision vs ~7% base rate; the 1-3m horizon is circuit-noise, no edge).
  * Universe = the FULL liquid universe (is_equity & ADV>floor). Futures-eligibility
    is NOT a gate here — it is a SEPARATE overlay flag (⚡) you can filter on.
  * Ensemble = rank-blend of three independent scorers that make different errors:
      - RULE : z(3m mom)+z(closeness to 52w-high)+z(liquidity growth)
      - ML   : HistGradientBoosting on the cross-sectional features
      - AI   : a neural net (MLP) on the same features
    plus a LIQUIDITY tilt (rank of ADV) — the wide universe's only real hazard is
    thin/manipulated names; the tilt recovers the drawdown (−35% → ~0) without
    re-imposing the eligibility wall.
  * No look-ahead: ML/AI train only on months whose 6-month outcome is already
    realised (ym ≤ entry−6); the entry cross-section is scored, never trained on.

Honest ceiling (from the walk-forward bake-off, OOS held-out half, K=15):
  precision ~27%, catches ~30% of all surgers, ~2.8× over the ~3.5y test half,
  ~0% drawdown. It is a WIDE-basket harvest — it catches ~a third of surgers and
  the fat tails pay; it does NOT snipe the individual mega-surgers (those are
  gated by pre-surge illiquidity and post-entry catalysts, not in price data).
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from pakterm import config, data
from analysis import futures_predictor as F

warnings.filterwarnings("ignore")

H = 6
LIQ_TILT = 0.5
_DROP = {"month", "rate_level", "rate_chg_3m", "cpi_yoy", "pkr_chg_3m", "oil_chg_3m", "mood_level"}

# Walk-forward bake-off, held-out OOS half (2019-2026), 6-month non-overlapping,
# gated. prec = precision on the realised top-15 (base rate ~7%); catch = % of ALL
# surgers (fwd6>=50%) caught; mult = cumulative over the ~3.5y test half; dd = maxDD.
BACKTEST = {
    "K15": [
        {"m": "Rule", "prec": 27, "catch": 29, "mult": "2.7x", "dd": 0},
        {"m": "ML", "prec": 24, "catch": 32, "mult": "2.6x", "dd": -2},
        {"m": "AI", "prec": 27, "catch": 30, "mult": "3.1x", "dd": 0},
        {"m": "Rule+ML", "prec": 25, "catch": 29, "mult": "2.7x", "dd": -1},
        {"m": "Rule+AI", "prec": 27, "catch": 35, "mult": "2.8x", "dd": 0},
        {"m": "ML+AI", "prec": 25, "catch": 31, "mult": "3.0x", "dd": 0},
        {"m": "Rule+ML+AI", "prec": 26, "catch": 33, "mult": "3.1x", "dd": 0},
    ],
    "K5": [
        {"m": "Rule", "prec": 25, "catch": 7, "mult": "1.2x", "dd": -20},
        {"m": "ML", "prec": 26, "catch": 12, "mult": "1.6x", "dd": -26},
        {"m": "AI", "prec": 27, "catch": 9, "mult": "1.4x", "dd": -16},
        {"m": "Rule+ML", "prec": 25, "catch": 11, "mult": "4.1x", "dd": -20},
        {"m": "Rule+AI", "prec": 28, "catch": 13, "mult": "4.9x", "dd": -12},
        {"m": "ML+AI", "prec": 24, "catch": 13, "mult": "5.8x", "dd": -9},
        {"m": "Rule+ML+AI", "prec": 28, "catch": 12, "mult": "4.4x", "dd": -10},
    ],
}


def _z(s):
    s = pd.Series(s, dtype=float)
    return (s - s.mean()) / (s.std() + 1e-9)


def _rank(s):
    return pd.Series(s).rank(pct=True).values


def _prep(min_adv: float):
    panel = F.feature_panel(min_adv)
    mp = panel.groupby(["symbol", "ym"]).last().reset_index()
    piv = mp.pivot(index="ym", columns="symbol", values="close").sort_index()
    fwd = piv.shift(-H) / piv - 1
    fl = fwd.reset_index().melt(id_vars="ym", var_name="symbol", value_name="fwd6")
    mp = mp.merge(fl, on=["symbol", "ym"], how="left")
    mp["liq"] = mp.is_equity & (mp.adv_20 > min_adv)
    feats = [f for f in F.FEATURES if f in mp.columns and f not in _DROP]
    return mp, feats


def _fit_predict(mp, feats, entry):
    """Return the entry-month cross-section with rule/ml/ai/ensemble scores."""
    from sklearn.neural_network import MLPRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer

    cur = mp[(mp.ym == entry) & (mp.liq)].copy()
    tr = mp[(mp.ym <= (entry - H)) & (mp.liq) & (mp.fwd6.notna())]
    if len(cur) < 15 or len(tr) < 200:
        return None
    use = [c for c in feats if tr[c].replace([np.inf, -np.inf], np.nan).nunique(dropna=True) >= 2]
    Xtr, ytr = tr[use].to_numpy(np.float32), tr.fwd6.to_numpy()
    Xcu = cur[use].to_numpy(np.float32)
    rule = (_z(cur.mom_3m) + _z(-cur.dist_252h) + _z(cur.adv_growth.fillna(0))).values
    hg = F._reg(); hg.fit(Xtr, ytr); ml = hg.predict(Xcu)
    mlp = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                        MLPRegressor(hidden_layer_sizes=(48, 16), max_iter=400,
                                     early_stopping=True, alpha=1e-3, random_state=0))
    mlp.fit(Xtr, ytr); ai = mlp.predict(Xcu)
    ens = (_rank(rule) + _rank(ml) + _rank(ai)) / 3.0 + LIQ_TILT * _rank(cur.log_adv)
    return cur.assign(_rule=_rank(rule), _ml=_rank(ml), _ai=_rank(ai), _ens=ens)


def _pick_list(scored, score_col, K, last_close):
    top = scored.nlargest(K, score_col)
    picks = []
    for rank_i, (_, r) in enumerate(top.iterrows(), 1):
        lc = float(last_close.get(r.symbol, np.nan))
        ret = (lc / float(r.close) - 1.0) if np.isfinite(lc) and r.close else None
        picks.append({
            "rank": rank_i, "symbol": r.symbol, "name": str(r["name"]),
            "sector": r.sector_name, "entry_close": round(float(r.close), 2),
            "last_close": None if not np.isfinite(lc) else round(lc, 2),
            "ret": None if ret is None else round(ret, 4),
            "futures_eligible": bool(r.eligible),
            "ens": round(float(r._ens), 3),
            "rule_pct": round(float(r._rule) * 100), "ml_pct": round(float(r._ml) * 100),
            "ai_pct": round(float(r._ai) * 100),
        })
    rr = [p["ret"] for p in picks if p["ret"] is not None]
    re = [p["ret"] for p in picks if p["ret"] is not None and p["futures_eligible"]]
    return {"picks": picks,
            "basket_ret": round(float(np.mean(rr)), 4) if rr else None,
            "basket_ret_eligible": round(float(np.mean(re)), 4) if re else None}


def predict(entry_ym, K: int = 15, min_adv: float = config.MIN_ADV) -> dict:
    mp, feats = _prep(min_adv)
    entry = pd.Period(entry_ym, "M")
    scored = _fit_predict(mp, feats, entry)
    if scored is None:
        return {"entry_month": str(entry), "picks": [], "by_method": {}}
    fwd_lo, fwd_hi = entry + 1, entry + H
    entry_date = scored.date.max()
    df = data.load_prices(); last_date = df.date.max()
    last_close = df.sort_values("date").groupby("symbol").close.last()
    methods = {"Ensemble": "_ens", "Rule": "_rule", "ML": "_ml", "AI": "_ai"}
    by_method = {name: _pick_list(scored, col, K, last_close) for name, col in methods.items()}
    ens = by_method["Ensemble"]
    return {
        "entry_month": str(entry), "entry_date": str(entry_date.date()),
        "as_of": str(last_date.date()), "days_held": int((last_date - entry_date).days),
        "forward_window": f"{fwd_lo} → {fwd_hi}", "K": K,
        "universe_n": int(len(scored)), "n_eligible": int(scored.eligible.sum()),
        "basket_ret": ens["basket_ret"], "basket_ret_eligible": ens["basket_ret_eligible"],
        "picks": ens["picks"],                       # default view = ensemble
        "by_method": by_method,                      # every method's picks + baskets
        "backtest_methods": BACKTEST,                # full walk-forward OOS bake-off
    }


def live_result(min_adv: float = config.MIN_ADV) -> dict:
    """Forward prediction made at the latest available month-end."""
    mp, _ = _prep(min_adv)
    el = mp[mp.liq]
    latest = data.latest_date()
    # anchor to the last COMPLETED month so entry price is fixed and returns
    # accumulate daily (rolls forward automatically as each month closes)
    completed = [m for m in sorted(el.ym.unique()) if el[el.ym == m].date.max() < latest]
    entry = completed[-1] if completed else sorted(el.ym.unique())[-1]
    out = predict(entry, K=15, min_adv=min_adv)
    # honest OOS scorecard from the walk-forward bake-off (held-out second half, K=15)
    out["scorecard"] = {
        "horizon_months": H, "basket_K": 15,
        "precision_oos": 0.27, "catch_rate_oos": 0.30,
        "cumulative_oos": "2.8x", "maxdd_oos": 0.0,
        "base_rate": 0.07,
        "method": "walk-forward, non-overlapping, gated, held-out second half of 2019-2026",
    }
    out["note"] = ("Forward 6-month surger picks — rule+ML+AI ensemble on the FULL liquid "
                   "universe, futures-eligibility as a SEPARATE overlay (⚡ = leverageable "
                   "via single-stock futures). A WIDE-basket harvest: expect to catch ~30% "
                   "of surgers OOS, not to snipe individual names. The mega-surgers are "
                   "gated by pre-surge illiquidity + post-entry catalysts (not in price "
                   "data). Research, not investment advice.")
    return out


if __name__ == "__main__":
    import json
    r = live_result()
    print(f"SURGER PREDICTOR | entry {r['entry_month']} (as of {r.get('as_of')}, {r.get('days_held')}d), "
          f"forward {r.get('forward_window')} | universe {r.get('universe_n')} "
          f"({r.get('n_eligible')} futures-eligible)")
    print(f"{'#':>2} {'sym':8} {'fut':>3} {'sector':22} {'entry':>8} {'now':>8} {'ret':>7} {'ens':>5} {'rule/ml/ai':>12}")
    for p in r["picks"]:
        rr = "" if p["ret"] is None else f"{p['ret']*100:+.1f}%"
        print(f"{p['rank']:>2} {p['symbol']:8} {'Y' if p['futures_eligible'] else '.':>3} "
              f"{str(p['sector'])[:22]:22} {p['entry_close']:>8.2f} "
              f"{'' if p['last_close'] is None else p['last_close']:>8} {rr:>7} {p['ens']:>5.2f} "
              f"{p['rule_pct']:>3}/{p['ml_pct']:>3}/{p['ai_pct']:>3}")
    print("\nLIVE basket so far, by method (all / futures-eligible only):")
    for name, d in r.get("by_method", {}).items():
        ba = "" if d["basket_ret"] is None else format(d["basket_ret"]*100, "+.1f")+"%"
        be = "" if d["basket_ret_eligible"] is None else format(d["basket_ret_eligible"]*100, "+.1f")+"%"
        print(f"  {name:12} {ba:>7} / {be:>7}")
    print("\nBACKTEST (walk-forward OOS half), K=15:")
    print(f"  {'method':12} {'prec':>4} {'catch':>6} {'mult':>6} {'maxDD':>6}")
    for row in r.get("backtest_methods", {}).get("K15", []):
        print(f"  {row['m']:12} {row['prec']:>3}% {row['catch']:>5}% {row['mult']:>6} {row['dd']:>+5}%")
    sc = r["scorecard"]
    print(f"\nOOS scorecard (K=15): precision {sc['precision_oos']*100:.0f}% (base {sc['base_rate']*100:.0f}%), "
          f"catch {sc['catch_rate_oos']*100:.0f}%, {sc['cumulative_oos']} test-half, maxDD {sc['maxdd_oos']*100:.0f}%")
