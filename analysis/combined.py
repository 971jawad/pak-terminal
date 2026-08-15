"""Can the tested edges be COMBINED into something reliably tradable?

Honest inventory first:
  * TRADABLE (survived OOS, both halves, net of cost): market TIMING (trend on the
    liquid basket). This is the only validated edge.
  * NOT tradable (real but weak/insignificant): cross-sectional factors, sector
    rotation, top-5 surger selection — spreads not significant, and futures carry
    kills them.
  * DESCRIPTIVE / in-sample only: bank-rate thesis, surge DNA, event studies.
  * CONTEXT (not backtestable here): FIPI/LIPI flows, news sentiment, mood.

You cannot reliably combine signals that aren't edges — stacking noise on one real
edge adds overfitting, not reliability. So the only honest "combination" is a
HIERARCHY: the timing signal decides WHEN you're invested; when in, you hold a
DIVERSIFIED basket (concentration lowered Sharpe); leverage scales the high-Sharpe
result, financed at the policy rate (the futures carry). The context layers are
human decision-support / small discretionary tilts, not mechanical alpha.

This module backtests exactly that hierarchy and reports whether it is tradable.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pakterm import config, data
from analysis.regime import ensemble_signal


def _perf(r: pd.Series, ppy: int = config.PPY) -> dict:
    r = r.dropna()
    eq = (1 + r).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    cagr = float(eq.iloc[-1] ** (ppy / len(r)) - 1)
    sharpe = float(r.mean() / (r.std() + 1e-12) * np.sqrt(ppy))
    return {"cagr": round(cagr, 3), "sharpe": round(sharpe, 2), "maxdd": round(dd, 3),
            "win": round(float((r > 0).mean()), 3)}


def strategies(min_adv: float = config.MIN_ADV, lev: float = 1.5,
               cost: float = 0.003) -> dict:
    """buy&hold vs timed(1x) vs timed+leverage, net of cost + policy-rate carry."""
    mkt = data.market_index(min_adv)
    idx = mkt.index
    pol = data.policy_rate_series(pd.DatetimeIndex(idx))
    pol = pol.reindex(idx).ffill().bfill()
    fin_daily = (1 + pol / 100) ** (1 / config.PPY) - 1     # financing/cash daily rate
    sig = ensemble_signal(mkt).shift(1).fillna(0.0).clip(0, 1)  # 1-day execution lag

    out = {}
    # buy & hold
    out["buy_hold"] = mkt.copy()
    # timed 1x: in-market earns mkt, out earns cash (T-bill), pay switch cost
    switch = sig.diff().abs().fillna(0.0)
    out["timed_1x"] = sig * mkt + (1 - sig) * fin_daily - switch * cost
    # timed + leverage L: position = L*signal; borrow (pos-1) financed at policy rate;
    # cash when pos<1; cost on exposure change
    pos = (lev * sig).clip(0, lev)
    borrow = (pos - 1).clip(lower=0)
    cashw = (1 - pos).clip(lower=0)
    lev_switch = pos.diff().abs().fillna(0.0)
    out[f"timed_{lev}x"] = pos * mkt + cashw * fin_daily - borrow * fin_daily - lev_switch * cost
    return {k: v for k, v in out.items()}


def report(min_adv: float = config.MIN_ADV, lev: float = 1.5) -> dict:
    s = strategies(min_adv, lev)
    idx = s["buy_hold"].index
    halves = {"2019-2022": (idx.min(), pd.Timestamp("2022-12-31")),
              "2023-2026": (pd.Timestamp("2023-01-01"), idx.max())}
    res = {"full": {k: _perf(v) for k, v in s.items()}, "halves": {}}
    for name, (lo, hi) in halves.items():
        res["halves"][name] = {k: _perf(v[(v.index >= lo) & (v.index <= hi)]) for k, v in s.items()}
    # carry hurdle context
    pol = data.policy_rate_series(pd.DatetimeIndex(idx)).reindex(idx).ffill().bfill()
    res["avg_policy_rate"] = round(float(pol.mean()), 2)
    res["current_signal"] = "RISK-ON" if ensemble_signal(data.market_index(min_adv)).iloc[-1] >= 0.5 else "RISK-OFF"
    return res


if __name__ == "__main__":
    r = report()
    print(f"avg policy (cash/carry) rate over sample: {r['avg_policy_rate']}%  |  now: {r['current_signal']}")
    print("\n=== FULL SAMPLE (net of cost + carry) ===")
    print(f"{'strategy':>12} {'CAGR':>8} {'Sharpe':>7} {'MaxDD':>8} {'Win':>6}")
    for k, m in r["full"].items():
        print(f"{k:>12} {m['cagr']:>+8.1%} {m['sharpe']:>7.2f} {m['maxdd']:>+8.1%} {m['win']:>6.0%}")
    for half, d in r["halves"].items():
        print(f"\n=== {half} (out-of-sample split) ===")
        for k, m in d.items():
            print(f"{k:>12} CAGR={m['cagr']:>+7.1%} Sharpe={m['sharpe']:>5.2f} DD={m['maxdd']:>+7.1%}")
