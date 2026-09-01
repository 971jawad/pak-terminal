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
from pakterm.trading_calendar import last_final_period, psx_holidays
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
    # rolled TODAY: the basket was entered at this very close, so nothing has
    # elapsed. Emit None (renders "—") rather than 0.0, which is indistinguishable
    # from a measured zero and from the RISK-OFF cash state.
    fresh = bool(last == entry)
    legs = []
    for p in pk["picks"]:
        s = df[df.symbol == p["symbol"]].set_index("date")["cumlog"]
        if entry in s.index and last in s.index:
            r = None if fresh else float(np.expm1(s.loc[last] - s.loc[entry]))
            legs.append({**p, "last_close": float(df[(df.symbol == p["symbol"]) & (df.date == last)]["close"].iloc[0]),
                         "ret": None if r is None else round(r, 3)})
    rr = [l["ret"] for l in legs if l["ret"] is not None]
    basket = round(float(np.mean(rr)), 3) if rr else None
    # if the gate was risk-off, the real position was cash, not the basket
    applied = None if fresh else (basket if pk["risk_on"] else 0.0)
    return {**pk, "as_of": str(last.date()), "days_held": int((last - entry).days),
            "legs": legs, "basket_ret": basket, "applied_ret": applied,
            "rolled_today": fresh,
            "note": ("entered at today's close — first mark next session" if fresh
                     else ("held basket" if pk["risk_on"] else
                           "gate was RISK-OFF -> real position is cash"))}


def closed_performance(entry_ym, exit_ym, min_adv: float = F.MIN_ADV) -> dict:
    """FINAL, exit-anchored result of a completed holding period (entry_ym month-end
    -> exit_ym month-end). Used so a just-closed basket's realised return is not lost
    the moment the live basket rolls."""
    pk = picks_for(entry_ym, min_adv=min_adv)
    if not pk["picks"]:
        return {}
    df = data.load_prices()
    entry = pd.Timestamp(pk["entry_date"])
    ex = df[df.date.dt.to_period("M") == pd.Period(exit_ym, "M")]["date"]
    if ex.empty:
        return {}
    exit_d = ex.max()
    if exit_d <= entry:
        return {}
    legs = []
    for p in pk["picks"]:
        s = df[df.symbol == p["symbol"]].set_index("date")["cumlog"]
        if entry in s.index and exit_d in s.index:
            legs.append({**p, "ret": round(float(np.expm1(s.loc[exit_d] - s.loc[entry])), 3)})
    if not legs:
        return {}
    basket = round(float(np.mean([l["ret"] for l in legs])), 3)
    return {"entry_month": str(entry_ym), "entry_date": str(entry.date()),
            "exit_month": str(exit_ym), "exit_date": str(exit_d.date()),
            "days_held": int((exit_d - entry).days), "risk_on": pk["risk_on"],
            "legs": legs, "basket_ret": basket,
            "applied_ret": basket if pk["risk_on"] else 0.0}


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


def _horizon_entry(last_full: pd.Period, H: int) -> pd.Period:
    """Most recent month <= last_full on horizon H's refresh grid.

    A horizon-H pick is entered once and HELD for H months, so it must refresh
    every H months — not every month like the 1m. The grid is anchored to
    January: entry months are those with (month-1) % H == 0. Because 12 % H == 0
    for H in {1,2,3,4,6}, the grid never skips across a year boundary (H=3 ->
    Jan/Apr/Jul/Oct, and Oct->Jan is exactly 3 months). H=1 -> every month."""
    m = last_full
    while (m.month - 1) % H != 0:
        m = m - 1
    return m


def _ml_basket(p, cuml, entry_p: pd.Period, H: int, entry_date, exit_date, mark: bool) -> dict:
    """Train horizon H on ALL data up to entry_p-H (no lookahead), pick the top-K
    from entry_p's cross-section, and — if `mark` — value the basket from
    entry_date to exit_date. Shared by live and closed, so a horizon that
    refreshes always recomputes fresh picks from the latest available data."""
    train = p[p.ym <= (entry_p - H)].dropna(subset=[f"fwd_{H}"])
    cur = p[p.ym == entry_p]
    if len(train) < 200 or len(cur) < F.TOPK:
        return {"legs": [], "basket_ret": None}
    m = F._reg(); m.fit(train[F.FEATURES].to_numpy(np.float32), train[f"fwd_{H}"].to_numpy())
    cur = cur.assign(score=m.predict(cur[F.FEATURES].to_numpy(np.float32)))
    legs = []
    for _, r in cur.nlargest(F.TOPK, "score").iterrows():
        ret = None
        if mark:
            try:
                ret = float(np.expm1(cuml.loc[(r.symbol, exit_date)] - cuml.loc[(r.symbol, entry_date)]))
            except KeyError:
                ret = None
        legs.append({"symbol": r.symbol, "sector": r.sector_name,
                     "entry": round(float(r.close), 2),
                     "ret": None if ret is None else round(ret, 3)})
    rr = [l["ret"] for l in legs if l["ret"] is not None]
    return {"legs": legs, "basket_ret": round(float(np.mean(rr)), 3) if rr else None}


def predictor_live(last_full, min_adv: float = F.MIN_ADV) -> dict:
    """ML futures-predictor top-5 per horizon, each marked to the latest close.

    Each horizon refreshes on ITS OWN cadence — 1m monthly, 2m every 2 months, 3m
    every 3 months — via _horizon_entry, so a 2m/3m basket is HELD through its
    horizon instead of being wrongly re-picked every month. Its return is measured
    from its own entry date (partial, mid-horizon) to now."""
    panel = F.feature_panel(min_adv)
    p = panel[panel.eligible].copy()
    df = data.load_prices(); last = df.date.max()
    cuml = df.set_index(["symbol", "date"])["cumlog"]
    lf = pd.Period(last_full, "M")
    out = {}
    for H in F.HORIZONS:
        entry_p = _horizon_entry(lf, H)
        cur = p[p.ym == entry_p]
        if cur.empty:
            out[str(H)] = {"legs": [], "basket_ret": None}
            continue
        entry_date = cur.date.max()
        fresh = bool(last == entry_date)      # rolled today: nothing elapsed -> None, not 0.0%
        b = _ml_basket(p, cuml, entry_p, H, entry_date, last, mark=not fresh)
        b.update({"entry_month": str(entry_p), "entry_date": str(entry_date.date()),
                  "matures_month": str(entry_p + H), "days_held": int((last - entry_date).days),
                  "rolled_today": fresh})
        out[str(H)] = b
    return {"as_of": str(last.date()), "by_horizon": out}


def predictor_closed(last_full, min_adv: float = F.MIN_ADV) -> dict:
    """FINAL result of every horizon whose hold JUST completed at last_full.

    A horizon H completes only when last_full is on H's refresh grid — i.e. a pick
    entered last_full-H matured exactly at last_full's month-end. So at an August
    close only the 1m completes (Jul->Aug); the 2m completes at Sep (Jul->Sep),
    the 3m at Oct (Jul->Oct). Exit-anchored, kept so a completed horizon's result
    is not lost the instant the live basket rolls."""
    panel = F.feature_panel(min_adv)
    p = panel[panel.eligible].copy()
    df = data.load_prices()
    lf = pd.Period(last_full, "M")
    ex = df[df.date.dt.to_period("M") == lf]["date"]
    if ex.empty:
        return {"by_horizon": {}}
    exit_d = ex.max()
    cuml = df.set_index(["symbol", "date"])["cumlog"]
    out = {}
    for H in F.HORIZONS:
        if _horizon_entry(lf, H) != lf:       # last_full is not a refresh month for H -> nothing completed
            continue
        entry_p = lf - H
        cur = p[p.ym == entry_p]
        if cur.empty:
            continue
        entry_date = cur.date.max()
        if exit_d <= entry_date:
            continue
        b = _ml_basket(p, cuml, entry_p, H, entry_date, exit_d, mark=True)
        b.update({"entry_month": str(entry_p), "entry_date": str(entry_date.date()),
                  "exit_month": str(lf), "exit_date": str(exit_d.date())})
        out[str(H)] = b
    return {"by_horizon": out, "exit_date": str(exit_d.date())}


def build_result(min_adv: float = F.MIN_ADV) -> dict:
    panel = F.feature_panel(min_adv)
    el = panel[panel.eligible]
    latest = data.latest_date()
    # live entry = the newest month with NO possible trading day left in it, so we
    # roll ON the last session of the month instead of waiting for the next month
    months = sorted(el.ym.unique())
    _fin = last_final_period(months, latest, psx_holidays())
    last_full = _fin if _fin is not None else months[-1]
    live = interim_performance(last_full, min_adv)
    # market baseline over the same live window (= buy&hold and, since RISK-ON, the timing strategies too)
    mkt = data.market_index(min_adv); loglvl = np.log1p(mkt).cumsum()
    mkt_since = None
    if live.get("entry_date"):
        ed = pd.Timestamp(live["entry_date"])
        if ed in loglvl.index:
            mkt_since = round(float(np.expm1(loglvl.iloc[-1] - loglvl.loc[ed])), 4)
    # the period that just closed — keep its FINAL realised result visible so it is
    # not lost the instant the live basket rolls on month-end
    last_closed = {}
    prev = [m for m in months if m < last_full]
    if prev:
        last_closed = closed_performance(prev[-1], last_full, min_adv)
        if last_closed:
            last_closed["predictor"] = predictor_closed(last_full, min_adv)
            ed = pd.Timestamp(last_closed["entry_date"]); xd = pd.Timestamp(last_closed["exit_date"])
            if ed in loglvl.index and xd in loglvl.index:
                last_closed["market"] = round(float(np.expm1(loglvl.loc[xd] - loglvl.loc[ed])), 4)
    return {"regime": timing_regime(min_adv), "backtest": backtest(min_adv),
            "live": live, "predictor_live": predictor_live(last_full, min_adv),
            "last_closed": last_closed,
            "market_live": mkt_since, "as_of": str(data.latest_date().date())}


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
