"""CONFLUENCE — the capstone decision engine, now in THREE variants so you can
compare like-for-like and trade the one that actually holds up out-of-sample.

Every name is scored by how many independent edges INTERSECT (regime-fit +
earnings turnaround + momentum + relative strength + liquidity) and tagged
REAL (earnings-backed, hold) / FAKEOUT (momentum but earnings falling, scalp) /
WATCH. That intersection read is shared by all three variants; what differs is
how the TRADEABLE BASKET is ranked:

  A · RAW        single confluence score (z-mom3 + z-near-high + z-rel-str +
                 z-liquidity + regime tilt - extension). The original engine.
  B · CONVICTION raw score + an earnings tilt: undo the extension penalty for
                 REAL breakouts and boost them, penalise FAKEOUTs. Uses a CURRENT
                 EPS snapshot, so the tilt is a forward overlay — see note.
  ★ · COMBINED   rank-averaged momentum ENSEMBLE (raw score + DNA low-vol/quality
                 factor + relative strength), carrying the REAL/FAKEOUT tags for
                 the conviction read. This is the honest best-of-both.

All three: futures-eligible universe, top-8, inverse-vol weighted, OPPORTUNITY-
GATED (trade only high-dispersion + risk-on months, else cash), 1-month hold,
net of cost, walk-forward 2019-2026 (OOS = held-out second half, no look-ahead).

Head-to-head OOS (this repo's harness, K=8):
                 Sharpe  Calmar   CAGR   maxDD   net+ (traded)
  A RAW           0.62    0.70    +16%    -23%      65%
  B CONVICTION*   0.68    0.90    +19%    -21%      69%   *honest point-in-time EPS
  ★ COMBINED      1.26    2.43    +38%    -16%      65%
The ensemble win is robust across basket size (K=5/8/10) and split point. The
earnings tilt adds little once timed honestly — its big apparent gain comes only
if you cheat with today's EPS (Sharpe 0.91 lookahead ceiling). So COMBINED ranks
on the momentum ensemble (the real edge) and keeps earnings as a conviction TAG.
~half the picks lose any month — the basket wins because winners outweigh losers.
Not investment advice.
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

from pakterm import config, data
from analysis import futures_predictor as F
from analysis import analysis_filter as AF
from analysis.regime import ensemble_signal

COST = 0.005

# Backtest metrics per variant — from _exp_confluence.py (walk-forward 2019-2026,
# OOS = held-out second half, opportunity-gated, top-8, inverse-vol, net cost).
BACKTESTS = {
    "raw": {
        "full": {"cagr": 0.10, "sharpe": 0.51, "calmar": 0.34, "maxdd": -0.30},
        "oos": {"cagr": 0.16, "sharpe": 0.62, "calmar": 0.70, "maxdd": -0.23},
        "pct_pos_months": 0.65,
        "method": "Single confluence score (z-mom3m + z-near-52wH + z-rel-str + z-liquidity "
                  "+ regime tilt - extension), inverse-vol top-8, opportunity-gated. Walk-"
                  "forward, OOS = held-out half, no look-ahead. Net-positive share = of "
                  "months actually traded.",
    },
    "conviction": {
        "full": {"cagr": 0.12, "sharpe": 0.55, "calmar": 0.39, "maxdd": -0.30},
        "oos": {"cagr": 0.19, "sharpe": 0.68, "calmar": 0.90, "maxdd": -0.21},
        "pct_pos_months": 0.69,
        "lookahead_sharpe": 0.91,
        "method": "Raw score + earnings tilt (boost REAL / penalise FAKEOUT). Backtested "
                  "with POINT-IN-TIME lagged ANNUAL EPS (no look-ahead) — barely above RAW, "
                  "matching the project's finding that annual earnings-momentum is weak. The "
                  "LIVE tab uses a CURRENT EPS snapshot (no point-in-time history exists), so "
                  "the live tilt is a forward overlay; with today's EPS the backtest would show "
                  "Sharpe ~0.91, but that is a look-ahead ceiling, not an achievable result.",
    },
    "combined": {
        "full": {"cagr": 0.21, "sharpe": 0.95, "calmar": 0.91, "maxdd": -0.23},
        "oos": {"cagr": 0.38, "sharpe": 1.26, "calmar": 2.43, "maxdd": -0.16},
        "pct_pos_months": 0.65,
        "method": "Rank-averaged momentum ENSEMBLE (raw confluence score + DNA low-vol/quality "
                  "factor + relative strength), inverse-vol top-8, opportunity-gated. Walk-"
                  "forward, OOS = held-out half, no look-ahead. Robust across K=5/8/10 and split "
                  "point; lower drawdown than RAW. Earnings shown as a conviction TAG, not a "
                  "score input (adding the tilt slightly hurt OOS). The honest best-of-both.",
    },
}


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


def _raw_score(g, sign):
    """Original single confluence score + the extension penalty component."""
    cyc = g.sector_name.map(AF.CYCLICAL).fillna(0).values
    ext = np.clip(_z(-g.dist_252h.fillna(-1)).values + _z(g.mom_1m.fillna(0)).values
                  + _z(g.maxup_1m.fillna(0)).values, 0, None)
    sc = (_z(g.mom_3m).values + _z(-g.dist_252h).values + _z(g.rel_str_3m.fillna(0)).values
          + _z(g.adv_growth.fillna(0)).values + 0.7 * sign * cyc - 0.5 * ext)
    return sc, ext


def _dna(g):
    """Low-vol / quality-momentum factor (from the Sniper engine)."""
    return (_z(-g.dist_252h) * 1.0 + _z(g.mom_6m) * 0.9 + _z(g.dd_6m) * 0.7 + _z(g.mom_12m) * 0.65
            + _z(g.mom_3m) * 0.6 + _z(g.rel_str_3m) * 0.6 - _z(g.vol_1m) * 0.5
            - _z(g.maxup_1m.fillna(0)) * 0.5).values


def _variant_score(variant, g, sign, fu):
    """Return the basket-ranking score for a variant over entry-month group g."""
    sc, ext = _raw_score(g, sign)
    if variant == "raw":
        return sc
    egv = g["symbol"].map(lambda s: (fu.get(s, {}) or {}).get("eps_growth_yoy"))
    real = (egv > 15).fillna(False).values.astype(float)
    fake = (egv < -15).fillna(False).values.astype(float)
    if variant == "conviction":
        return sc + 0.5 * ext * real + 1.2 * real - 1.0 * fake
    if variant == "combined":
        return (_rank(sc) + _rank(_dna(g)) + _rank(g.rel_str_3m.fillna(0).values)) / 3.0
    raise ValueError(variant)


def _tag(eg, ext=None, mom3=None):
    if eg is not None and eg > 15:
        return "REAL"
    if eg is not None and eg < -15 and (mom3 or 0) > 0.10:
        return "FAKEOUT"
    if ext is not None and ext > 2.5:
        return "FAKEOUT"
    return "WATCH"


def _basket(variant, ge, sign, fu, lastc):
    """Top-8 inverse-vol basket for a variant, marked to the latest close."""
    score = _variant_score(variant, ge, sign, fu)
    top = ge.assign(_s=score).nlargest(8, "_s").copy()
    vol = top["vol_1m"].fillna(top["vol_1m"].median()).clip(lower=1e-4).values
    w = (1.0 / vol); w = w / w.sum(); top = top.assign(weight=w)
    picks = []
    for i, (_, r) in enumerate(top.iterrows(), 1):
        lc = float(lastc.get(r.symbol, np.nan))
        ret = (lc / float(r.close) - 1.0) if np.isfinite(lc) and r.close else None
        eg = (fu.get(r.symbol, {}) or {}).get("eps_growth_yoy")
        picks.append({"rank": i, "symbol": r.symbol, "sector": r.sector_name,
                      "weight": round(float(r.weight), 4), "entry_close": round(float(r.close), 2),
                      "last_close": None if not np.isfinite(lc) else round(lc, 2),
                      "ret": None if ret is None else round(ret, 4),
                      "eps_growth": eg, "tag": _tag(eg, mom3=r.get("mom_3m"))})
    rr = np.array([p["ret"] for p in picks if p["ret"] is not None])
    ww = np.array([p["weight"] for p in picks if p["ret"] is not None])
    basket = float(np.sum(ww * rr) / ww.sum()) if len(rr) else None
    return picks, (round(basket, 4) if basket is not None else None)


def live_result(min_adv: float = config.MIN_ADV) -> dict:
    panel = F.feature_panel(min_adv)
    cur = panel[panel.date == panel.date.max()]
    mac = data.load_macro_monthly(); mac.index = mac.index.to_period("M")
    reg = AF.regime_state(mac, cur.ym.iloc[0]); sign = reg["sign"]
    rate = float(mac["policy_rate"].dropna().iloc[-1]) if mac["policy_rate"].notna().any() else None
    favored = ("banks / autos (high-rate)" if sign < 0 else
               "cement / refinery / real-estate / autos (easing)" if sign > 0 else "no strong tilt")
    fu = _fund()

    # ---- shared edge-intersection read (variant-independent) ----
    g = cur[cur.eligible].copy()
    sc, ext = _raw_score(g, sign)
    g = g.assign(sc=sc, ext=ext)
    rows = []
    for _, r in g.iterrows():
        edges = []
        cyc = AF.CYCLICAL.get(r.sector_name, 0)
        if sign * cyc > 0: edges.append("regime")
        eg = (fu.get(r.symbol, {}) or {}).get("eps_growth_yoy")
        if eg is not None and eg > 15: edges.append("earnings+")
        if (r.mom_3m or 0) > 0.10 and (r.dist_252h or -1) > -0.15: edges.append("momentum")
        if (r.rel_str_3m or 0) > 0: edges.append("rel-str")
        if (r.adv_growth or 0) > 0.3: edges.append("liquidity")
        rows.append({"symbol": r.symbol, "sector": r.sector_name, "confluence": len(edges),
                     "edges": edges, "tag": _tag(eg, r.ext, r.mom_3m), "eps_growth": eg,
                     "mom_3m": round(float(r.mom_3m or 0), 3), "sc": float(r.sc)})
    rows.sort(key=lambda x: (-x["confluence"], -x["sc"]))

    # ---- opportunity gate (shared) ----
    sig = ensemble_signal(data.market_index(min_adv))
    expo = float(sig.asof(g.date.max())) if len(sig) else 1.0
    if not np.isfinite(expo): expo = 0.0
    mp = panel.groupby(["symbol", "ym"]).last().reset_index()
    disp_cur = float(mp[(mp.ym == cur.ym.iloc[0]) & mp.eligible]["mom_1m"].std())
    disp_hist = mp[mp.eligible].groupby("ym")["mom_1m"].std()
    disp_med = float(disp_hist.expanding(min_periods=6).median().iloc[-1])
    trade = (disp_cur >= disp_med) and (expo >= 0.5)

    # ---- entry month + per-variant baskets ----
    latest = data.latest_date()
    el = mp[mp.eligible]
    completed = [m for m in sorted(el.ym.unique()) if el[el.ym == m].date.max() < latest]
    entry = completed[-1] if completed else sorted(el.ym.unique())[-1]
    ge = mp[(mp.ym == entry) & mp.eligible].copy()
    sign_e = AF.regime_state(mac, entry)["sign"]
    df = data.load_prices(); last_date = df.date.max()
    lastc = df.sort_values("date").groupby("symbol").close.last()
    entry_date = ge.date.max()

    labels = {"raw": "A · Raw score", "conviction": "B · Conviction (earnings-tilted)",
              "combined": "★ Combined ensemble"}
    variants = {}
    for key in ("raw", "conviction", "combined"):
        picks, bret = _basket(key, ge, sign_e, fu, lastc)
        variants[key] = {"label": labels[key], "picks": picks, "basket_ret": bret,
                         "backtest": BACKTESTS[key]}

    return {
        "as_of": str(last_date.date()), "entry_month": str(entry), "entry_date": str(entry_date.date()),
        "regime": {"label": reg["label"], "sign": sign, "favored": favored, "policy_rate": rate},
        "opportunity": {"trade": bool(trade), "dispersion": round(disp_cur, 3),
                        "disp_median": round(disp_med, 3), "risk_on": bool(expo >= 0.5)},
        "action": "TRADE" if trade else "SIT OUT (in cash)",
        "high_conviction": [r for r in rows if r["confluence"] >= 3][:15],
        "n_conviction": int(sum(1 for r in rows if r["confluence"] >= 3)),
        "variants": variants,
        "recommended": "combined",
        "note": ("Three ranking variants over the same futures-eligible universe, opportunity-"
                 "gated and inverse-vol weighted. COMBINED (rank-averaged momentum ensemble) is "
                 "the honest out-of-sample winner (Sharpe 1.26 vs RAW 0.62), robust across basket "
                 "size and split. The earnings tilt (CONVICTION) barely helps once timed honestly; "
                 "its big apparent gain needs today's EPS, which is look-ahead. So COMBINED ranks "
                 "on momentum and keeps earnings as a conviction TAG. ~half of picks lose in any "
                 "month — the basket nets positive because winners outweigh losers. Not advice."),
    }


if __name__ == "__main__":
    r = live_result()
    rg = r["regime"]; o = r["opportunity"]
    print(f"CONFLUENCE as of {r['as_of']} | regime {rg['label']} -> favours {rg['favored']}")
    print(f"  {r['action']}  (dispersion {o['dispersion']} vs {o['disp_median']}, "
          f"{'risk-on' if o['risk_on'] else 'risk-off'})")
    print(f"  {r['n_conviction']} high-conviction (3+ edges) names")
    for key, v in r["variants"].items():
        bt = v["backtest"]["oos"]
        label = v["label"].encode("ascii", "replace").decode()
        print(f"\n  [{label}]  OOS Sharpe {bt['sharpe']} | Calmar {bt['calmar']} | "
              f"maxDD {bt['maxdd']*100:.0f}%  | basket {r['entry_month']} -> {v['basket_ret']}")
        for p in v["picks"]:
            rr = "" if p["ret"] is None else f"{p['ret']*100:+.1f}%"
            print(f"    {p['symbol']:9} {p['tag']:8} w{p['weight']*100:>4.1f}%  {rr:>7}")
