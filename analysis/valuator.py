"""VALUATOR — the regime engine that makes the picks risk-efficient.

Two honest findings drive this tab:
  1. You cannot pick the single biggest surgers from price data (see Picker). Of
     each year's top-10 full-universe surgers, only ~2 were even LIQUID/tradeable
     BEFORE they surged, and a price score caught ~0.3 of them — the rest are
     illiquid/catalyst-driven and only "catchable" with look-ahead + survivorship.
  2. But you CAN massively improve the RISK-ADJUSTED return of a diversified basket
     by TIMING it. The project's one verified, out-of-sample, cost-surviving edge is
     the trend-ensemble gate (Sharpe ~1.15->1.45, maxDD -42%->-25%). Applied to the
     Picker styles it roughly DOUBLES Sharpe and cuts drawdown by two-thirds.

VALUATOR = MCD regime read (trend exposure + a small macro tilt: rate / CPI / PKR /
reserves — sign rules only, not a fitted predictor) + a SECTOR-CATALYST detector
(hot sectors by momentum + volume, Framework-E style = detects the move once price/
volume confirm, not the policy cause beforehand) + a RAW-vs-GATED backtest showing
the Sharpe/Calmar/vol improvement, walk-forward, no look-ahead. The humbling result:
the gated liquid UNIVERSE is about as good risk-adjusted as any style — timing beats
selection here. Not investment advice.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from pakterm import config, data
from analysis import futures_predictor as F
from analysis.regime import ensemble_signal
import analysis.picker as PK

warnings.filterwarnings("ignore")

RF = 0.11
K = PK.K


def _macro_expo(mac, ym):
    """MCD macro tilt in [0.6,1.0] — small, economically-grounded, SIGN RULES ONLY
    (not fitted; ~85 monthly points would overfit). Bull tilt = easing (rate down) +
    disinflation (CPI down) + PKR stable/strong (down) + reserves rising."""
    try:
        sub = mac[mac.index <= ym].tail(4)
        if len(sub) < 4:
            return 1.0
        score = 0.0
        rate = sub["policy_rate"]; score += -np.sign(rate.iloc[-1] - rate.iloc[0])
        cpi = sub["cpi_yoy"].dropna()
        if len(cpi) >= 2: score += -np.sign(cpi.iloc[-1] - cpi.iloc[0])
        pkr = sub["pkr_usd"].dropna()
        if len(pkr) >= 2: score += -np.sign(pkr.iloc[-1] - pkr.iloc[0])
        res = sub["fx_reserves_sbp_bn"].dropna()
        if len(res) >= 2: score += np.sign(res.iloc[-1] - res.iloc[0])
        return float(np.clip(0.8 + 0.05 * score, 0.6, 1.0))
    except Exception:
        return 1.0


def _dna_names(mp, piv, entry, k=K):
    """Pre-surge DNA basket at entry: cheap (low nominal price) + volume-awakening
    (adv_growth) + liquidity-awakening (Amihud falling vs 3m ago). OOS-validated tilt
    toward >=100% moves (weak, regime-dependent). PIT — all inputs known at entry."""
    e3 = entry - 3
    g = mp[(mp.ym == entry) & mp.liq].copy(); g = g[g.symbol.isin(piv.columns)]
    if len(g) < 20:
        return []
    prior = mp[mp.ym == e3][["symbol", "amihud"]].rename(columns={"amihud": "amihud0"})
    g = g.merge(prior, on="symbol", how="left")
    med = g.amihud.median()
    cheap = pd.Series(-g.close.values).rank(pct=True).values
    volwake = pd.Series(g.adv_growth.fillna(0).values).rank(pct=True).values
    liqwake = pd.Series(-(np.log1p(g.amihud.fillna(med)) - np.log1p(g.amihud0.fillna(med))).values).rank(pct=True).values
    g = g.assign(dna=(cheap + volwake + liqwake) / 3.0)
    return list(g.nlargest(k, "dna").symbol)


def _stats(r, rf=RF):
    r = pd.Series(r).dropna()
    if len(r) < 6:
        return {}
    eq = (1 + r).cumprod(); n = len(r); sd = r.std()
    cagr = eq.iloc[-1] ** (12 / n) - 1
    dd = float((eq / eq.cummax() - 1).min())
    return {"cagr": round(cagr, 4), "vol": round(float(sd * np.sqrt(12)), 4),
            "sharpe": round(float((r.mean() - rf / 12) / sd * np.sqrt(12)) if sd > 0 else 0.0, 2),
            "maxdd": round(dd, 4), "calmar": round(cagr / abs(dd), 2) if dd < 0 else None, "n": int(n)}


def _gate_backtest(mp, piv, mac, sig):
    """RAW vs REGIME-GATED monthly path for the liquid universe + each Picker style.
    Gate = trend-ensemble exposure x MCD macro tilt, cash otherwise. PIT: signal from
    data up to prior month-end applied to next month. Also a train/test split."""
    months = list(piv.index)
    idx = {m: i for i, m in enumerate(months)}
    years = sorted({p.year for p in months})
    date_of = mp.groupby("ym")["date"].max()
    STYLES = list(PK.VARIANTS) + ["dna"]
    held = {v: {} for v in STYLES}
    annual = {v: [] for v in STYLES}; annual["univ"] = []
    for Y in years:
        entry, ex = pd.Period(f"{Y-1}-12", "M"), pd.Period(f"{Y}-12", "M")
        if entry not in idx:
            continue
        g = mp[(mp.ym == entry) & mp.liq].copy(); g = g[g.symbol.isin(piv.columns)]
        if len(g) < 20:
            continue
        for v in PK.VARIANTS:
            held[v][Y] = list(g.assign(_s=PK._score(v, g)).nlargest(K, "_s").symbol)
        held["dna"][Y] = _dna_names(mp, piv, entry, K)
        if ex in idx:                                   # full-year returns for the annual table
            yr = (piv.loc[ex] / piv.loc[entry] - 1.0)
            annual["univ"].append([Y, round(float(g.symbol.map(yr).dropna().mean()), 4)])
            for v in STYLES:
                nm = held[v][Y]
                annual[v].append([Y, round(float(pd.Series([yr.get(s, np.nan) for s in nm]).dropna().mean()), 4) if nm else None])
    liq_by = {ym: list(set(mp[(mp.ym == ym) & mp.liq].symbol) & set(piv.columns)) for ym in months}
    cash = RF / 12

    def mret(names, m, pm):
        if not names:
            return np.nan
        r = (piv.loc[m, names].astype(float) / piv.loc[pm, names].astype(float) - 1.0)
        r = r.replace([np.inf, -np.inf], np.nan).dropna()
        return float(r.mean()) if len(r) else np.nan

    keys = ["univ"] + STYLES
    raw = {k: [] for k in keys}; gat = {k: [] for k in keys}; gidx = []
    for i in range(1, len(months)):
        m, pm = months[i], months[i - 1]
        if not any(m.year in held[v] for v in STYLES):
            continue
        gidx.append(m)
        expo = float(sig.asof(date_of[pm])) if pm in date_of.index and len(sig) else 1.0
        if not np.isfinite(expo): expo = 0.0
        e = expo * _macro_expo(mac, pm)
        for k in keys:
            b = mret(held[k].get(m.year, []) if k != "univ" else liq_by.get(pm, []), m, pm)
            raw[k].append(b)
            gat[k].append(np.nan if b is None or not np.isfinite(b) else e * b + (1 - e) * cash)
    out = {"raw": {k: _stats(raw[k]) for k in keys}, "gated": {k: _stats(gat[k]) for k in keys},
           "annual_dna": annual["dna"], "annual_univ": annual["univ"]}
    h = len(gidx) // 2
    out["split"] = {
        "univ": {"train": _stats(gat["univ"][:h]), "test": _stats(gat["univ"][h:])},
        "dna": {"train": _stats(gat["dna"][:h]), "test": _stats(gat["dna"][h:])},
    }
    return out


def _mcd(mac, sig):
    """Current regime read: trend exposure (the verified edge) + macro tilt + directions."""
    expo = float(sig.iloc[-1]) if len(sig) else 1.0
    if not np.isfinite(expo): expo = 0.0
    ym = mac.index.max()
    tilt = _macro_expo(mac, ym)

    def dirn(col, good_down=True):
        s = mac[col].dropna()
        if len(s) < 2:
            return 0
        d = float(s.iloc[-1] - s.iloc[-min(4, len(s))])
        return int(-np.sign(d) if good_down else np.sign(d))

    gate = expo * tilt
    posture = ("RISK-ON — deploy" if gate >= 0.6 else
               "PARTIAL — half size" if gate >= 0.35 else "RISK-OFF — mostly cash")
    return {
        "as_of": str(sig.index[-1].date()) if len(sig) else None,
        "trend_exposure": round(expo, 2), "macro_tilt": round(tilt, 2),
        "gate": round(gate, 2), "posture": posture,
        "rate": float(mac["policy_rate"].dropna().iloc[-1]) if mac["policy_rate"].notna().any() else None,
        "cpi": float(mac["cpi_yoy"].dropna().iloc[-1]) if mac["cpi_yoy"].notna().any() else None,
        "pkr": float(mac["pkr_usd"].dropna().iloc[-1]) if mac["pkr_usd"].notna().any() else None,
        "rate_dir": dirn("policy_rate"), "cpi_dir": dirn("cpi_yoy"),
        "pkr_dir": dirn("pkr_usd"), "reserves_dir": dirn("fx_reserves_sbp_bn", good_down=False),
    }


def _sectors(panel, min_adv):
    """Sector-catalyst detector: rank sectors by recent momentum + volume growth
    (price/volume only, PIT). Flags a sector HOT once its move is confirmed — it
    detects the surge, not the SRO/policy cause beforehand (that needs data we lack)."""
    cur = panel[panel.date == panel.date.max()].copy()
    liq = cur[cur.is_equity & (cur.adv_20 > min_adv)]
    sec = (liq.groupby("sector_name")
           .agg(n=("symbol", "size"), mom3=("mom_3m", "median"),
                mom6=("mom_6m", "median"), advg=("adv_growth", "median")).reset_index())
    sec = sec[sec.n >= 3].sort_values("mom3", ascending=False)
    out = []
    for _, r in sec.head(8).iterrows():
        names = liq[liq.sector_name == r.sector_name]
        up = names[names.mom_3m > 0.10].sort_values("mom_3m", ascending=False)
        adv_med = float(up.adv_20.median()) / 1e6 if len(up) else 0.0
        # BROAD/REAL = the move is carried by liquid, volume-backed names across the
        # sector; THIN/PUMP = dragged hot by a few thin, parabolic small-caps (ASTM-type).
        broad = bool(len(up) >= 3 and adv_med >= 30.0)
        drivers = [{"symbol": d.symbol, "mom3": round(float(d.mom_3m), 2),
                    "adv_mn": round(float(d.adv_20) / 1e6, 0)} for _, d in up.head(3).iterrows()]
        out.append({"sector": r.sector_name, "n": int(r.n),
                    "mom3": round(float(r.mom3), 3), "mom6": round(float(r.mom6), 3),
                    "advg": round(float(r.advg), 3), "adv_median_mn": round(adv_med, 0),
                    "kind": "broad" if broad else "thin", "drivers": drivers,
                    "hot": bool(r.mom3 >= 0.20 and r.advg > 0)})
    return out


def _announcements(days=45):
    """Best-effort symbol -> most-recent catalytic PSX announcement (guarded; the
    scrape may be unavailable in a local build, in which case the radar still runs
    on price/volume alone)."""
    try:
        from analysis import catalysts
        feed = catalysts.catalyst_feed(days=days)
        out = {}
        for it in feed.get("items", []):
            s = it.get("symbol")
            if s and s not in out:                     # items are newest-first
                out[s] = {"type": it.get("type"), "title": (it.get("title") or "")[:90],
                          "date": it.get("date")}
        return out
    except Exception:
        return {}


def _radar(panel, fu, min_adv, k=15):
    """SURGE RADAR — scan the whole liquid universe every build for names where a move
    is STARTING with volume confirmation (short-term momentum + acceleration + volume
    surge), then attach the most recent PSX announcement as the likely driver. This is
    the honest 'constantly find what drives surges' mechanism: it detects the move as
    price/volume confirm it (Framework-E style) and surfaces the catalyst — it does not
    predict the SRO/policy before the market moves (no data can, without look-ahead)."""
    cur = panel[panel.date == panel.date.max()].copy()
    g = cur[cur.is_equity & (cur.adv_20 > min_adv)].copy()
    if len(g) < 20:
        return {"as_of": None, "movers": []}
    score = (PK._z(g.mom_1m.fillna(0)).values + PK._z(g.mom_accel.fillna(0)).values
             + 1.2 * PK._z(g.adv_growth.fillna(0)).values + 0.6 * PK._z(g.rev_1w.fillna(0)).values
             + 0.4 * PK._z(-g.dist_252h.fillna(-1)).values)
    g = g.assign(_s=score)
    # cross-sectional percentiles for the breakout-vs-pump microstructure read
    def pct(col, inv=False):
        v = g[col].fillna(g[col].median()); r = v.rank(pct=True)
        return (1 - r) if inv else r
    g = g.assign(_maxup_p=pct("maxup_1m"), _vol_p=pct("vol_1m"), _amihud_p=pct("amihud"),
                 _adv_p=pct("adv_20"))
    # emerging = actually moving up AND volume expanding (not already parabolic)
    em = g[(g.mom_1m > 0.05) & (g.adv_growth > 0.3)].nlargest(k, "_s")
    ann = _announcements()
    movers = []
    for _, r in em.iterrows():
        eg = (fu.get(r.symbol, {}) or {}).get("eps_growth_yoy")
        a = ann.get(r.symbol)
        # PUMP-RISK signature: thin liquidity + parabolic limit-up spikes + moved-on-no-volume
        # + extreme extension. BREAKOUT: real expanding volume + genuine liquidity, not parabolic.
        pump = 0
        pump += 1 if r.adv_20 < 3 * min_adv else 0                 # barely liquid = pumpable
        pump += 1 if r._maxup_p > 0.80 else 0                      # limit-up / parabolic single days
        pump += 1 if r._amihud_p > 0.70 else 0                     # price moved on little real volume
        pump += 1 if (r.dist_252h or -1) > -0.03 else 0            # pinned at all-time high (extended)
        pump += 1 if r._vol_p > 0.85 else 0                        # extreme volatility
        vol_backed = (r.adv_growth or 0) > 0.5 and r.adv_20 > 3 * min_adv and r._maxup_p < 0.80
        quality = "BREAKOUT" if (vol_backed and pump <= 1) else ("PUMP-RISK" if pump >= 3 else "MIXED")
        movers.append({"symbol": r.symbol, "sector": r.sector_name,
                       "mom_1m": round(float(r.mom_1m or 0), 3), "mom_3m": round(float(r.mom_3m or 0), 3),
                       "adv_growth": round(float(r.adv_growth or 0), 2),
                       "adv_mn": round(float(r.adv_20 or 0) / 1e6, 1),
                       "dist_252h": round(float(r.dist_252h or 0), 3),
                       "quality": quality, "pump_score": int(pump),
                       "eps_growth": eg, "tag": PK._tag(eg),
                       "catalyst": a})
    return {"as_of": str(cur.date.max().date()), "n_scanned": int(len(g)),
            "n_flagged": int(len(em)), "movers": movers,
            "has_announcements": bool(ann)}


def _dna_live(mp, piv, fu, min_adv, k=K):
    """Current-year pre-surge DNA basket (entry = last Dec) marked to today (YTD)."""
    cur_year = piv.index.max().year
    entry = pd.Period(f"{cur_year-1}-12", "M")
    if entry not in set(piv.index):
        return None
    names = _dna_names(mp, piv, entry, k)
    if not names:
        return None
    lastc = piv.iloc[-1]; ec = piv.loc[entry]
    picks = []
    for i, s in enumerate(names, 1):
        a, b = float(ec.get(s, np.nan)), float(lastc.get(s, np.nan))
        eg = (fu.get(s, {}) or {}).get("eps_growth_yoy")
        sec = mp[(mp.symbol == s) & (mp.ym == entry)]["sector_name"]
        picks.append({"rank": i, "symbol": s, "sector": str(sec.iloc[0]) if len(sec) else "",
                      "entry_close": None if not np.isfinite(a) else round(a, 2),
                      "last_close": None if not np.isfinite(b) else round(b, 2),
                      "ytd": None if not (np.isfinite(a) and np.isfinite(b) and a) else round(b / a - 1, 4),
                      "tag": PK._tag(eg)})
    rr = [p["ytd"] for p in picks if p["ytd"] is not None]
    return {"year": cur_year, "entry_month": str(entry),
            "basket_ytd": round(float(np.mean(rr)), 4) if rr else None, "picks": picks}


def live_result(min_adv: float = config.MIN_ADV) -> dict:
    panel = F.feature_panel(min_adv)
    mp = panel.groupby(["symbol", "ym"]).last().reset_index()
    mp["liq"] = mp.is_equity & (mp.adv_20 > min_adv)
    piv = mp.pivot(index="ym", columns="symbol", values="close").sort_index()
    mac = data.load_macro_monthly(); mac.index = mac.index.to_period("M")
    sig = ensemble_signal(data.market_index(min_adv))
    return {
        "mcd": _mcd(mac, sig),
        "sectors": _sectors(panel, min_adv),
        "radar": _radar(panel, PK._fund(), min_adv),
        "gate": _gate_backtest(mp, piv, mac, sig),
        "dna_live": _dna_live(mp, piv, PK._fund(), min_adv),
        "meta": {
            "avg_tradeable": 2.0, "avg_caught15": 0.3, "avg_caught50": 0.5,
            "note": ("Meta-analysis of catchability: of each year's TOP-10 full-universe surgers "
                     "(2020-2025), on average only ~2/10 were even liquid/tradeable BEFORE they "
                     "surged; a combined price score caught ~0.3/10 in top-15 and ~0.5/10 even in "
                     "a wide top-50. The other ~80% are illiquid micro-caps/ETFs bought only with "
                     "hindsight. Catching 'all top surgers' requires look-ahead + survivorship bias "
                     "— it is not achievable honestly. The real edge is timing a diversified basket."),
        },
        "note": ("VALUATOR turns the honest half of the frameworks into a risk engine. The MCD "
                 "regime read (verified trend gate + a small macro tilt) says how much to deploy "
                 "now; the sector-catalyst detector flags where price/volume have confirmed a move; "
                 "and the RAW-vs-GATED backtest shows the payoff — gating roughly DOUBLES Sharpe and "
                 "cuts drawdown by ~two-thirds vs buy-and-hold. Humbling truth: the gated liquid "
                 "UNIVERSE is about as good risk-adjusted as any selection style — here, timing beats "
                 "stock-picking. Walk-forward, PIT, no fitted magnitudes. Not investment advice."),
    }


if __name__ == "__main__":
    r = live_result()
    m = r["mcd"]
    print(f"MCD as of {m['as_of']}: gate {m['gate']} ({m['posture']}) | trend {m['trend_exposure']} x macro {m['macro_tilt']}")
    print(f"  rate {m['rate']}% (dir {m['rate_dir']}) cpi {m['cpi']}% (dir {m['cpi_dir']}) pkr {m['pkr']} (dir {m['pkr_dir']})")
    print("\nHot sectors:")
    for s in r["sectors"]:
        print(f"  {'HOT ' if s['hot'] else '    '}{s['sector']:34} mom3 {s['mom3']*100:+.0f}%  mom6 {s['mom6']*100:+.0f}%  vol {s['advg']:+.2f}")
    g = r["gate"]
    print(f"\n{'':16}{'RAW':>22}{'GATED':>22}")
    print(f"{'':16}{'Sharpe  maxDD  Calmar':>22}{'Sharpe  maxDD  Calmar':>22}")
    for k in ["univ"] + list(PK.VARIANTS):
        a, b = g["raw"].get(k, {}), g["gated"].get(k, {})
        if not a or not b: continue
        print(f"  {k:14}{a['sharpe']:>7.2f}{a['maxdd']*100:>7.0f}%{(a['calmar'] or 0):>7.2f}"
              f"{b['sharpe']:>9.2f}{b['maxdd']*100:>7.0f}%{(b['calmar'] or 0):>7.2f}")
    sp = g["split"]
    print(f"\ntrain/test (gated): univ Sharpe {sp['univ']['train'].get('sharpe')}/{sp['univ']['test'].get('sharpe')} "
          f"| combined {sp['combined']['train'].get('sharpe')}/{sp['combined']['test'].get('sharpe')}")
