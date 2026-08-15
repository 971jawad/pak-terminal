"""The locked-in strategy: rule-based momentum top-5, gated by the timing signal.

This is the honest optimum from the full research arc (ML overfit; simpler rule
beat it; two-stage/residual/sector didn't help; the TIMING GATE halved drawdown
and doubled compounding; offense tweaks added nothing; defense filters only cut
return). It is a fat-tailed, moonshot-carried convex basket with ~-30% drawdown —
NOT a money-printer, unlevered, size small. Backtest is in-sample-ish over ~7y /
1-2 regime cycles and depends on the (fragile) timing edge. Not investment advice.

  score  = z(mom_3m) + z(-dist_from_52w_high) + z(adv_growth)   [cross-sectional]
  picks  = top-5 futures-eligible by score
  gate   = hold picks only when the trend signal is RISK-ON, else cash (T-bill)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from pakterm import config, data
from analysis import futures_predictor as F
from analysis.regime import ensemble_signal, timing_regime

COST = 0.005


def _z(s):
    s = pd.Series(s, dtype=float)
    return (s - s.mean()) / (s.std() + 1e-9)


def _score(g: pd.DataFrame) -> np.ndarray:
    return _z(g["mom_3m"]).values + _z(-g["dist_252h"]).values + _z(g["adv_growth"].fillna(0)).values


def picks_for(entry_ym, k: int = 5, min_adv: float = F.MIN_ADV) -> dict:
    """Top-5 rule-based picks made at the end of `entry_ym`, with the timing gate state."""
    panel = F.feature_panel(min_adv)
    g = panel[panel.eligible & (panel.ym == pd.Period(entry_ym, "M"))].copy()
    if len(g) < k:
        return {"entry_month": str(entry_ym), "picks": [], "risk_on": None}
    g["score"] = _score(g)
    top = g.nlargest(k, "score")
    entry_date = g.date.max()
    sig = ensemble_signal(data.market_index(min_adv))
    expo = float(sig.asof(entry_date)) if len(sig) else 1.0
    return {
        "entry_month": str(entry_ym), "entry_date": str(entry_date.date()),
        "risk_on": bool(expo >= 0.5), "exposure": round(expo, 2),
        "picks": [{"symbol": r.symbol, "name": str(r["name"]), "sector": r.sector_name,
                   "score": round(float(r.score), 3), "mom_3m": round(float(r.mom_3m), 3),
                   "entry_close": round(float(r.close), 2)} for _, r in top.iterrows()],
    }


def interim_performance(entry_ym, min_adv: float = F.MIN_ADV) -> dict:
    """Mark the entry_ym picks to the latest available close (partial-period read)."""
    pk = picks_for(entry_ym, min_adv=min_adv)
    if not pk["picks"]:
        return {**pk, "legs": [], "basket_ret": None}
    df = data.load_prices()
    entry = pd.Timestamp(pk["entry_date"]); last = df.date.max()
    legs = []
    for p in pk["picks"]:
        s = df[df.symbol == p["symbol"]].set_index("date")["cumlog"]
        if entry in s.index and last in s.index:
            r = float(np.expm1(s.loc[last] - s.loc[entry]))
            legs.append({**p, "last_close": float(df[(df.symbol == p["symbol"]) & (df.date == last)]["close"].iloc[0]),
                         "ret": round(r, 3)})
    basket = round(float(np.mean([l["ret"] for l in legs])), 3) if legs else None
    # if the gate was risk-off, the real position was cash, not the basket
    applied = basket if pk["risk_on"] else 0.0
    return {**pk, "as_of": str(last.date()), "days_held": int((last - entry).days),
            "legs": legs, "basket_ret": basket, "applied_ret": applied,
            "note": "held basket" if pk["risk_on"] else "gate was RISK-OFF -> real position is cash"}


def backtest(min_adv: float = F.MIN_ADV) -> dict:
    """Gated top-5 stats per horizon (net of cost+carry, non-overlapping, walk-forward)."""
    panel = F.feature_panel(min_adv)
    p = panel[panel.eligible].copy()
    mac = data.load_macro_monthly(); mac.index = mac.index.to_period("M")
    sig = ensemble_signal(data.market_index(min_adv))
    months = sorted(p.ym.unique())
    out = {}
    for H in (1, 2, 3):
        ents = [m for m in months if p[p.ym == m][f"fwd_{H}"].notna().any()][::H]
        per, eq, eqs = [], 1.0, []
        for m in ents:
            g = p[p.ym == m].dropna(subset=[f"fwd_{H}"]).copy()
            if len(g) < 15:
                continue
            g["s"] = _score(g)
            top = g.nlargest(5, "s")
            rate = float(mac["policy_rate"].reindex([m]).iloc[0]) if m in mac.index else 11.0
            carry = rate / 100 * H / 12
            risk_on = float(sig.asof(g.date.max())) >= 0.5 if len(sig) else True
            net = (top[f"fwd_{H}"].mean() - COST - carry) if risk_on else carry
            per.append(net); eq *= (1 + net); eqs.append(eq)
        per, eqs = np.array(per), np.array(eqs)
        dd = float((eqs / np.maximum.accumulate(eqs) - 1).min()) if len(eqs) else np.nan
        out[H] = {"n": len(per), "avg_per_period": round(float(per.mean()), 4),
                  "pct_positive": round(float((per > 0).mean()), 3),
                  "mult_1usd": round(float(eqs[-1]), 2), "max_dd": round(dd, 3)}
    return out


def build_result(min_adv: float = F.MIN_ADV) -> dict:
    panel = F.feature_panel(min_adv)
    el = panel[panel.eligible]
    latest = data.latest_date()
    # live entry = last COMPLETED month-end (exclude the current partial month)
    completed = [m for m in sorted(el.ym.unique()) if el[el.ym == m].date.max() < latest]
    last_full = completed[-1] if completed else sorted(el.ym.unique())[-1]
    live = interim_performance(last_full, min_adv)
    return {"regime": timing_regime(min_adv), "backtest": backtest(min_adv),
            "live": live, "as_of": str(data.latest_date().date())}


if __name__ == "__main__":
    import sys
    ym = sys.argv[1] if len(sys.argv) > 1 else "2026-07"
    r = interim_performance(ym)
    print(f"=== AUGUST PREDICTION (picks made {r.get('entry_date')}, gate {'RISK-ON' if r['risk_on'] else 'RISK-OFF'}) ===")
    for l in r["legs"]:
        print(f"  {l['symbol']:8} {l['sector'][:22]:22}  entry {l['entry_close']:>8.2f} -> {l['last_close']:>8.2f}  {l['ret']:+.1%}")
    print(f"  basket so far ({r.get('days_held')}d, thru {r.get('as_of')}): {r['basket_ret']:+.1%}  [{r['note']}]")
    print("\n=== BACKTEST (gated top-5, per horizon) ===")
    for H, s in backtest().items():
        print(f"  {H}m: avg/pd {s['avg_per_period']:+.1%}  %pos {s['pct_positive']*100:.0f}%  $1->${s['mult_1usd']}  maxDD {s['max_dd']*100:.0f}%  (n={s['n']})")
