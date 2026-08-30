"""PICKER — the "year-end race": which names surge most over a CALENDAR YEAR.

Rebuilt on an ANNUAL cadence and tested year-by-year (the honest way to judge a
"top surger of the year" model). Once per year you pick at the START of the year
using ONLY prior-year data (features as of that December — no look-ahead), hold
the whole year, and are judged at Dec 31. We replay that decision for every year
2020-2025 and show it live, plus this year's (2026) actual start-of-year picks and
their year-to-date return.

Universe = FULL LIQUID (is_equity & ADV>floor) — surgers are often not futures-
eligible. Basket = top-15, EQUAL-weight (upside, not risk-parity — inverse-vol
would suppress the volatile names that surge). Three framework styles + combined:
  A TURNAROUND  beaten-down (deep 6m drawdown / near 6m-low) now bouncing
  B LEADERS     raw 3/6/12m momentum + rel-strength - parabolic extension
  C MOM-QUALITY DNA low-vol / quality-momentum factor
  * COMBINED    rank-averaged ensemble of the three

HONEST FINDINGS (from the year-by-year backtest, computed live below):
  * No style reliably beats just owning the whole liquid universe — over 6 years
    Leaders/Quality roughly TIE the equal-weight universe (~2.7x); Turnaround
    trails. The models only decisively won in the 2024 mega-bull.
  * The WINNING STYLE ROTATES with the regime: Turnaround in recovery years
    (2020/2023), Quality loses least in down years (2021/2022), Leaders/Combined
    win strong bulls (2024/2025).
  * Top-decile HIT RATE ~7-12% ~= the 10% base rate — you CANNOT reliably pick
    THE single biggest surger from price data (the project's long-standing result;
    mega-surgers are catalyst/illiquidity-driven, not in price). The baskets DO
    contain monsters (best pick averages +150-190%), just diluted across 15 names.
  * Fundamental/catalyst screens (turnaround earnings, sector catalysts, war/policy
    shocks) need point-in-time data this project lacks -> forward paper-ledger only.
Treat Picker as a diversified, regime-aware candidate list, not a surger sniper.
Not investment advice.
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd

from pakterm import config, data
from analysis import futures_predictor as F

warnings.filterwarnings("ignore")

K = 15
LIQ_TILT = 0.5
TOP_FRAC = 0.10          # "top surger of the year" = top 10% of that year's returns


def _z(s):
    s = pd.Series(s, dtype=float)
    return (s - s.mean()) / (s.std() + 1e-9)


def _rank(s):
    return pd.Series(s, dtype=float).rank(pct=True).values


def _fund():
    try:
        return {r["symbol"]: r for r in json.loads((config.DATA / "fundamentals_universe.json").read_text())}
    except Exception:
        return {}


def _ext(g):
    return np.clip(_z(-g.dist_252h.fillna(-1)).values + _z(g.mom_1m.fillna(0)).values
                   + _z(g.maxup_1m.fillna(0)).values, 0, None)


def _turnaround(g):
    return (_z(-g.dd_6m.fillna(0)).values + _z(-g.dist_6mlow.fillna(0)).values
            + 1.2 * _z(g.mom_1m.fillna(0)).values + _z(g.mom_accel.fillna(0)).values
            + 0.8 * _z(g.adv_growth.fillna(0)).values + 0.4 * _z(g.rev_1w.fillna(0)).values)


def _leaders(g):
    return (_z(g.mom_3m).values + _z(g.mom_6m).values + 0.7 * _z(g.mom_12m).values
            + _z(g.rel_str_3m.fillna(0)).values - 0.5 * _ext(g))


def _quality(g):
    return (_z(-g.dist_252h) * 1.0 + _z(g.mom_6m) * 0.9 + _z(g.dd_6m) * 0.7 + _z(g.mom_12m) * 0.65
            + _z(g.mom_3m) * 0.6 + _z(g.rel_str_3m) * 0.6 - _z(g.vol_1m) * 0.5
            - _z(g.maxup_1m.fillna(0)) * 0.5).values


VARIANTS = ("turnaround", "leaders", "quality", "combined")
LABELS = {"turnaround": "A · Turnaround", "leaders": "B · Leaders",
          "quality": "C · Mom-quality", "combined": "★ Combined"}


def _score(variant, g):
    liq = LIQ_TILT * _rank(g.log_adv.values)          # hazard control in the wide universe
    if variant == "turnaround":
        return _rank(_turnaround(g)) + liq
    if variant == "leaders":
        return _rank(_leaders(g)) + liq
    if variant == "quality":
        return _rank(_quality(g)) + liq
    if variant == "combined":
        return (_rank(_leaders(g)) + _rank(_quality(g)) + _rank(_turnaround(g))) / 3.0 + liq
    raise ValueError(variant)


def _tag(eg):
    if eg is None:
        return "—"
    if eg > 15:
        return "REAL"
    if eg < -15:
        return "FADING"
    return "WATCH"


def _prep(min_adv):
    panel = F.feature_panel(min_adv)
    mp = panel.groupby(["symbol", "ym"]).last().reset_index()
    mp["liq"] = mp.is_equity & (mp.adv_20 > min_adv)
    piv = mp.pivot(index="ym", columns="symbol", values="close").sort_index()
    return mp, piv


def _annual(mp, piv, k=K):
    """Year-by-year walk-forward: pick at start of year (Dec of Y-1), hold to Dec Y."""
    years = sorted({p.year for p in piv.index})
    rows, comp = [], {v: 1.0 for v in VARIANTS}; comp["univ"] = 1.0
    hit = {v: [] for v in VARIANTS}; beat = {v: [] for v in VARIANTS}; best = {v: [] for v in VARIANTS}
    for Y in years:
        entry, exit_ = pd.Period(f"{Y-1}-12", "M"), pd.Period(f"{Y}-12", "M")
        if entry not in piv.index or exit_ not in piv.index:
            continue
        yr = (piv.loc[exit_] / piv.loc[entry] - 1.0)
        g = mp[(mp.ym == entry) & mp.liq].copy()
        g = g[g.symbol.isin(yr.dropna().index)]
        if len(g) < 20:
            continue
        g["yret"] = g.symbol.map(yr)
        g = g.dropna(subset=["yret"])
        thr = float(g.yret.quantile(1 - TOP_FRAC))
        row = {"year": Y, "n": int(len(g)), "univ": round(float(g.yret.mean()), 4)}
        comp["univ"] *= (1 + float(g.yret.mean()))
        vals = {}
        for v in VARIANTS:
            top = g.assign(_s=_score(v, g)).nlargest(k, "_s")
            r = float(top.yret.mean()); row[v] = round(r, 4); vals[v] = r
            comp[v] *= (1 + r)
            hit[v].append(float((top.yret >= thr).mean()))
            beat[v].append(1.0 if r > float(g.yret.mean()) else 0.0)
            best[v].append(float(top.yret.max()))
        row["winner"] = max(vals, key=vals.get)
        rows.append(row)
    summary = {"n_years": len(rows), "univ_mean": round(float(np.mean([r["univ"] for r in rows])), 4) if rows else None,
               "univ_comp": round(comp["univ"], 2)}
    for v in VARIANTS:
        summary[v] = {
            "mean": round(float(np.mean([r[v] for r in rows])), 4) if rows else None,
            "comp": round(comp[v], 2),
            "beat_rate": round(float(np.mean(beat[v])), 2) if beat[v] else None,
            "hit_rate": round(float(np.mean(hit[v])), 3) if hit[v] else None,
            "best_avg": round(float(np.mean(best[v])), 3) if best[v] else None,
        }
    return rows, summary


def _pathstats(mp, piv, rf=0.11, k=K):
    """Monthly path of each style's ANNUALLY-rebalanced top-15 (buy each Jan, hold,
    mark monthly) -> Sharpe / annualised vol / maxDD / Calmar. Universe = equal-weight
    monthly return of the liquid set (the benchmark). rf = SBP policy ~11%."""
    months = list(piv.index)
    idx = {m: i for i, m in enumerate(months)}
    years = sorted({p.year for p in months})
    held = {v: {} for v in VARIANTS}
    for Y in years:
        entry = pd.Period(f"{Y-1}-12", "M")
        if entry not in idx:
            continue
        g = mp[(mp.ym == entry) & mp.liq].copy()
        g = g[g.symbol.isin(piv.columns)]
        if len(g) < 20:
            continue
        for v in VARIANTS:
            held[v][Y] = list(g.assign(_s=_score(v, g)).nlargest(k, "_s").symbol)
    liq_by = {ym: list(set(mp[(mp.ym == ym) & mp.liq].symbol) & set(piv.columns)) for ym in months}

    def mret(names, m, pm):
        if not names:
            return np.nan
        r = (piv.loc[m, names].astype(float) / piv.loc[pm, names].astype(float) - 1.0)
        r = r.replace([np.inf, -np.inf], np.nan).dropna()
        return float(r.mean()) if len(r) else np.nan

    ser = {v: [] for v in VARIANTS}; ser["univ"] = []; ridx = []
    for i in range(1, len(months)):
        m, pm = months[i], months[i - 1]
        if not any(m.year in held[v] for v in VARIANTS):
            continue
        ridx.append(m)
        for v in VARIANTS:
            ser[v].append(mret(held[v].get(m.year, []), m, pm))
        ser["univ"].append(mret(liq_by.get(pm, []), m, pm))
    out = {}
    for key in list(VARIANTS) + ["univ"]:
        r = pd.Series(ser[key], index=pd.PeriodIndex(ridx, freq="M")).dropna()
        if len(r) < 6:
            out[key] = {}; continue
        eq = (1 + r).cumprod(); n = len(r); sd = r.std()
        cagr = eq.iloc[-1] ** (12 / n) - 1
        dd = float((eq / eq.cummax() - 1).min())
        out[key] = {"cagr": round(cagr, 4), "vol": round(float(sd * np.sqrt(12)), 4),
                    "sharpe": round(float((r.mean() - rf / 12) / sd * np.sqrt(12)) if sd > 0 else 0.0, 2),
                    "maxdd": round(dd, 4), "calmar": round(cagr / abs(dd), 2) if dd < 0 else None,
                    "n": int(n)}
    return out


def _current_picks(mp, piv, fu, k=K):
    """This year's start-of-year picks (entry = last Dec) marked to the latest close (YTD)."""
    cur_year = piv.index.max().year
    entry = pd.Period(f"{cur_year-1}-12", "M")
    if entry not in piv.index:
        return None
    df = data.load_prices(); last_date = df.date.max()
    lastc = df.sort_values("date").groupby("symbol").close.last()
    entry_close = piv.loc[entry]
    g = mp[(mp.ym == entry) & mp.liq].copy()
    g = g[g.symbol.isin(entry_close.dropna().index)]
    if len(g) < 20:
        return None
    ytd = g.symbol.map(lambda s: (float(lastc.get(s, np.nan)) / float(entry_close.get(s, np.nan)) - 1.0)
                       if np.isfinite(lastc.get(s, np.nan)) and entry_close.get(s, 0) else np.nan)
    g["ytd"] = ytd.values
    variants = {}
    for v in VARIANTS:
        top = g.assign(_s=_score(v, g)).nlargest(k, "_s")
        picks = []
        for i, (_, r) in enumerate(top.iterrows(), 1):
            eg = (fu.get(r.symbol, {}) or {}).get("eps_growth_yoy")
            ec = float(entry_close.get(r.symbol, np.nan)); lc = float(lastc.get(r.symbol, np.nan))
            picks.append({"rank": i, "symbol": r.symbol, "sector": r.sector_name,
                          "entry_close": None if not np.isfinite(ec) else round(ec, 2),
                          "last_close": None if not np.isfinite(lc) else round(lc, 2),
                          "ytd": None if not np.isfinite(r.ytd) else round(float(r.ytd), 4),
                          "eps_growth": eg, "tag": _tag(eg)})
        rr = [p["ytd"] for p in picks if p["ytd"] is not None]
        variants[v] = {"label": LABELS[v], "picks": picks,
                       "basket_ytd": round(float(np.mean(rr)), 4) if rr else None}
    uni_ytd = float(np.nanmean(g["ytd"].values))
    return {"year": cur_year, "entry_month": str(entry), "as_of": str(last_date.date()),
            "universe_ytd": round(uni_ytd, 4) if np.isfinite(uni_ytd) else None,
            "n_universe": int(len(g)), "variants": variants}


def live_result(min_adv: float = config.MIN_ADV) -> dict:
    fu = _fund()
    mp, piv = _prep(min_adv)
    rows, summary = _annual(mp, piv)
    summary["risk"] = _pathstats(mp, piv)
    current = _current_picks(mp, piv, fu)
    return {
        "annual": rows, "summary": summary, "current": current,
        "recommended": "combined",
        "note": ("PICKER is the year-end race, run once a year and judged Dec 31, tested year-by-"
                 "year (no look-ahead). Honest result: NO style reliably beats owning the whole "
                 "liquid universe — Leaders/Quality roughly tie it over 6 years, Turnaround trails; "
                 "the winner ROTATES with the regime. Top-decile hit rate ~= the 10% base rate, so "
                 "you can't reliably pick THE single biggest surger from price data — the baskets "
                 "hold monsters but diluted across 15 names. Combined (3-way ensemble) is the "
                 "steadiest all-weather choice. Not investment advice."),
        "forward_note": ("The frameworks' fundamental/catalyst edges (earnings turnarounds, sector "
                         "policy shocks, war/oil moves) need point-in-time data this project lacks, so "
                         "they are NOT in this backtest. EPS shows only as a live REAL/WATCH tag. To "
                         "test catalysts honestly, log this year's picks at today's prices and mark "
                         "them forward — never re-pick with hindsight."),
    }


if __name__ == "__main__":
    r = live_result()
    s = r["summary"]
    print(f"ANNUAL year-by-year ({s['n_years']} years) — full-year return of top-{K}, held to Dec:")
    print(f"{'year':6}{'univ':>8}{'turn':>8}{'lead':>8}{'qual':>8}{'comb':>8}  winner")
    for row in r["annual"]:
        print(f"{row['year']:<6}{row['univ']*100:>7.0f}%{row['turnaround']*100:>7.0f}%"
              f"{row['leaders']*100:>7.0f}%{row['quality']*100:>7.0f}%{row['combined']*100:>7.0f}%  {row['winner']}")
    print(f"\ncompounded: univ {s['univ_comp']}x | "
          + " | ".join(f"{v} {s[v]['comp']}x" for v in VARIANTS))
    rk = s.get("risk", {})
    print(f"\nrisk (monthly path, {rk.get('univ',{}).get('n','?')} months): "
          f"{'style':11} {'CAGR':>6} {'Vol':>6} {'Sharpe':>7} {'maxDD':>6} {'Calmar':>7}")
    for key in ["univ"] + list(VARIANTS):
        d = rk.get(key, {})
        if not d: continue
        print(f"  {key:11} {d['cagr']*100:>5.0f}% {d['vol']*100:>5.0f}% {d['sharpe']:>7.2f} "
              f"{d['maxdd']*100:>5.0f}% {(d['calmar'] if d['calmar'] is not None else 0):>7.2f}")
    cur = r["current"]
    if cur:
        print(f"\n{cur['year']} picks (entry {cur['entry_month']} -> {cur['as_of']}), universe YTD {cur['universe_ytd']*100:.0f}%:")
        for v, d in cur["variants"].items():
            print(f"  [{d['label'].encode('ascii','replace').decode()}] basket YTD "
                  f"{d['basket_ytd']*100:+.0f}%: {', '.join(p['symbol'] for p in d['picks'])}")
