"""PICKER — the "Alpha Engine" frameworks, operationalised honestly and run as
comparable style variants over the same futures-eligible universe.

The pasted frameworks (turnaround quality-floor, entry-timing, year-end race,
sector-catalyst) lean on point-in-time FUNDAMENTALS and CATALYST data that this
project does not have — fundamentals exist only as a CURRENT snapshot, so any
value/catalyst screen applied to the past is look-ahead. What IS point-in-time
(prices, volume, liquidity, drawdown, momentum, relative strength, volatility,
regime) is what we can honestly walk-forward. So the frameworks are mapped to
price-expressible styles and the earnings layer is kept as a LIVE tag only:

  A · TURNAROUND (Framework E)  deep 6m drawdown / near 6m-low, now bouncing
                               (mom_1m up, momentum accel, volume surge) — mean-reversion.
  B · LEADERS    (Framework F)  raw 3/6/12m momentum + rel-strength - parabolic
                               extension penalty — the year-end race.
  C · MOM-QUALITY               DNA low-vol / quality-momentum factor (from Sniper).
  ★ · COMBINED                  rank-averaged ensemble of all three — best of both.

All: futures-eligible, top-8, inverse-vol weighted, OPPORTUNITY-GATED (trade only
high-dispersion + risk-on months, else cash), 1-month hold, net cost, walk-forward
2019-2026 (OOS = held-out half, no look-ahead).

Head-to-head OOS (this repo's harness, K=8):
                 Sharpe  Calmar   CAGR   maxDD   net+ (traded)
  A TURNAROUND    0.58    0.72    +15%    -21%      62%
  B LEADERS       1.44    2.98    +45%    -15%      73%
  C MOM-QUALITY   1.29    2.17    +34%    -16%      69%
  ★ COMBINED      1.55    3.11    +42%    -14%      81%
The 3-way ensemble wins and is robust across basket size (K=5/8/10) and split.
Turnaround is honestly the weakest — PSX rewards continuation and punishes fading —
but it diversifies the ensemble, which is why COMBINED still edges LEADERS. Adding
today's EPS as a conviction tilt (a LOOK-AHEAD ceiling) reaches only Sharpe ~1.34,
BELOW the honest ensemble — so fundamentals add nothing here; earnings stay a TAG.
~half of picks lose any month; the basket nets positive because winners outweigh
losers. The fundamental/catalyst screens can only be forward-tested — start a dated
paper ledger. Not investment advice.
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

# Backtest metrics per variant — from _exp_picker.py (walk-forward 2019-2026, OOS =
# held-out second half, opportunity-gated, top-8, inverse-vol, net cost).
BACKTESTS = {
    "turnaround": {
        "full": {"cagr": 0.07, "sharpe": 0.38, "calmar": 0.20, "maxdd": -0.34},
        "oos": {"cagr": 0.15, "sharpe": 0.58, "calmar": 0.72, "maxdd": -0.21},
        "pct_pos_months": 0.62,
        "method": "Framework E — deep 6m drawdown / near 6m-low, now bouncing (mom_1m up + "
                  "momentum accel + volume surge + short reversal). Mean-reversion. Honestly the "
                  "weakest: PSX rewards continuation and punishes fading, so buying dips underperforms.",
    },
    "leaders": {
        "full": {"cagr": 0.25, "sharpe": 1.09, "calmar": 1.21, "maxdd": -0.20},
        "oos": {"cagr": 0.45, "sharpe": 1.44, "calmar": 2.98, "maxdd": -0.15},
        "pct_pos_months": 0.73,
        "method": "Framework F — raw 3/6/12m momentum + relative strength, minus a parabolic-"
                  "extension penalty (down-size names spiking at their highs). The year-end race; "
                  "the strongest single style on PSX.",
    },
    "quality": {
        "full": {"cagr": 0.18, "sharpe": 0.97, "calmar": 0.87, "maxdd": -0.21},
        "oos": {"cagr": 0.34, "sharpe": 1.29, "calmar": 2.17, "maxdd": -0.16},
        "pct_pos_months": 0.69,
        "method": "DNA low-vol / quality-momentum factor (from Sniper): room below 52w-high + "
                  "6/12m momentum + shallow drawdown + rel-strength, minus volatility and up-day "
                  "spikes. Smoother than raw Leaders.",
    },
    "combined": {
        "full": {"cagr": 0.23, "sharpe": 1.12, "calmar": 1.03, "maxdd": -0.22},
        "oos": {"cagr": 0.42, "sharpe": 1.55, "calmar": 3.11, "maxdd": -0.14},
        "pct_pos_months": 0.81,
        "lookahead_sharpe": 1.34,
        "method": "Rank-averaged ENSEMBLE of all three styles (Turnaround + Leaders + Mom-quality), "
                  "inverse-vol top-8, opportunity-gated. Best OOS Sharpe and lowest drawdown; robust "
                  "across K=5/8/10 and split point. Turnaround is weak alone but diversifies the "
                  "ensemble. Adding today's EPS as a conviction tilt (a look-ahead ceiling) reaches "
                  "only Sharpe ~1.34 — BELOW this — so earnings stay a TAG, not a score input.",
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


def _variant_score(variant, g):
    if variant == "turnaround":
        return _turnaround(g)
    if variant == "leaders":
        return _leaders(g)
    if variant == "quality":
        return _quality(g)
    if variant == "combined":
        return (_rank(_leaders(g)) + _rank(_quality(g)) + _rank(_turnaround(g))) / 3.0
    raise ValueError(variant)


def _tag(eg, mom3=None):
    if eg is not None and eg > 15:
        return "REAL"
    if eg is not None and eg < -15 and (mom3 or 0) > 0.10:
        return "FAKEOUT"
    return "WATCH"


def _basket(variant, ge, fu, lastc):
    top = ge.assign(_s=_variant_score(variant, ge)).nlargest(8, "_s").copy()
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
                      "eps_growth": eg, "tag": _tag(eg, r.get("mom_3m"))})
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

    # opportunity gate (shared)
    g = cur[cur.eligible].copy()
    sig = ensemble_signal(data.market_index(min_adv))
    expo = float(sig.asof(g.date.max())) if len(sig) else 1.0
    if not np.isfinite(expo): expo = 0.0
    mp = panel.groupby(["symbol", "ym"]).last().reset_index()
    disp_cur = float(mp[(mp.ym == cur.ym.iloc[0]) & mp.eligible]["mom_1m"].std())
    disp_hist = mp[mp.eligible].groupby("ym")["mom_1m"].std()
    disp_med = float(disp_hist.expanding(min_periods=6).median().iloc[-1])
    trade = (disp_cur >= disp_med) and (expo >= 0.5)

    # entry month + per-variant baskets
    latest = data.latest_date()
    el = mp[mp.eligible]
    completed = [m for m in sorted(el.ym.unique()) if el[el.ym == m].date.max() < latest]
    entry = completed[-1] if completed else sorted(el.ym.unique())[-1]
    ge = mp[(mp.ym == entry) & mp.eligible].copy()
    df = data.load_prices(); last_date = df.date.max()
    lastc = df.sort_values("date").groupby("symbol").close.last()
    entry_date = ge.date.max()

    labels = {"turnaround": "A · Turnaround (Framework E)", "leaders": "B · Leaders (Framework F)",
              "quality": "C · Mom-quality (DNA)", "combined": "★ Combined ensemble"}
    variants = {}
    for key in ("turnaround", "leaders", "quality", "combined"):
        picks, bret = _basket(key, ge, fu, lastc)
        variants[key] = {"label": labels[key], "picks": picks, "basket_ret": bret,
                         "backtest": BACKTESTS[key]}

    return {
        "as_of": str(last_date.date()), "entry_month": str(entry), "entry_date": str(entry_date.date()),
        "regime": {"label": reg["label"], "sign": sign, "favored": favored, "policy_rate": rate},
        "opportunity": {"trade": bool(trade), "dispersion": round(disp_cur, 3),
                        "disp_median": round(disp_med, 3), "risk_on": bool(expo >= 0.5)},
        "action": "TRADE" if trade else "SIT OUT (in cash)",
        "variants": variants,
        "recommended": "combined",
        "note": ("PICKER runs the Alpha-Engine frameworks as four comparable styles over the "
                 "futures-eligible universe, opportunity-gated and inverse-vol weighted. COMBINED "
                 "(3-way rank-averaged ensemble) is the honest OOS winner (Sharpe 1.55) with the "
                 "lowest drawdown, robust across basket size and split. TURNAROUND is the weakest — "
                 "PSX rewards continuation, punishes fading — but diversifies the ensemble. The "
                 "frameworks' FUNDAMENTAL/CATALYST screens need point-in-time data this project "
                 "lacks, so they are NOT in the backtest; EPS is shown only as a live REAL/WATCH "
                 "tag and must be forward-tested via a dated paper ledger. Even a look-ahead EPS "
                 "tilt (Sharpe ~1.34) trails the honest momentum ensemble. Not investment advice."),
        "forward_note": ("Fundamental turnaround (quality floor, Piotroski, D/E) and the sector-"
                         "catalyst detector are NOT backtestable here — no point-in-time fundamentals. "
                         "Track them forward: log today's Combined picks with today's prices, mark to "
                         "market on each revisit, never re-pick with hindsight. After ~3-4 months that "
                         "ledger yields the first honest live Sharpe."),
    }


if __name__ == "__main__":
    r = live_result()
    rg = r["regime"]; o = r["opportunity"]
    print(f"PICKER as of {r['as_of']} | regime {rg['label']} -> favours {rg['favored']}")
    print(f"  {r['action']}  (dispersion {o['dispersion']} vs {o['disp_median']}, "
          f"{'risk-on' if o['risk_on'] else 'risk-off'})")
    for key, v in r["variants"].items():
        bt = v["backtest"]["oos"]
        label = v["label"].encode("ascii", "replace").decode()
        print(f"\n  [{label}]  OOS Sharpe {bt['sharpe']} | Calmar {bt['calmar']} | "
              f"maxDD {bt['maxdd']*100:.0f}%  | basket {r['entry_month']} -> {v['basket_ret']}")
        for p in v["picks"]:
            rr = "" if p["ret"] is None else f"{p['ret']*100:+.1f}%"
            print(f"    {p['symbol']:9} {p['tag']:8} w{p['weight']*100:>4.1f}%  {rr:>7}")
