"""Market Mood — a 5-level Fear/Greed gauge for PSX, built from market internals
(the CNN Fear & Greed approach: momentum, trend, breadth, volatility, drawdown).

Two honest design choices:
  * Components are normalised by a TRAILING rolling percentile (252d), so the
    gauge is self-calibrating and the history has no look-ahead — the value on
    day t uses only data up to day t. That makes the history backtestable.
  * We DO test whether mood predicts forward returns (contrarian: extreme fear ->
    higher forward returns). But we report the REAL in-sample result with its
    caveats. We do NOT curve-fit a "perfect" backtest — that is the exact
    self-deception this whole project refuses. See mood_backtest().
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pakterm import config, data

BANDS = [(0, 20, "Extreme Fear"), (20, 40, "Fear"), (40, 60, "Neutral"),
         (60, 80, "Greed"), (80, 100, "Extreme Greed")]


def _roll_pct(s: pd.Series, win: int = 252, minp: int = 90) -> pd.Series:
    """Trailing percentile rank (0-100) of the last value within a rolling window.
    No look-ahead: each point ranks itself against the preceding `win` days."""
    return s.rolling(win, min_periods=minp).apply(
        lambda a: (a[-1] >= a).mean() * 100, raw=True)


def mood_components(min_adv: float = config.MIN_ADV) -> pd.DataFrame:
    """Daily 0-100 sub-scores (higher = greedier). Trailing-percentile normalised."""
    mkt = data.market_index(min_adv)
    lvl = (1 + mkt).cumprod()
    br = data.market_breadth(min_adv)

    # 1) momentum: index vs its 125d MA
    mom = lvl / lvl.rolling(125, min_periods=40).mean() - 1
    # 2) trend strength: fraction of 4 MAs the index sits above (ensemble exposure)
    def _above(n): return (lvl > lvl.rolling(n).mean()).astype(float)
    trend = pd.concat([_above(n) for n in (20, 50, 100, 200)], axis=1).mean(axis=1)
    # 3) breadth: 20d average share of liquid names up
    breadth = br.rolling(20, min_periods=8).mean()
    # 4) low-volatility = greed: inverse of 20d realised vol
    vol = mkt.rolling(20, min_periods=8).std()
    # 5) safe-haven / drawdown: index distance from trailing 1y high (0 = at high)
    dd = lvl / lvl.rolling(252, min_periods=60).max() - 1

    comp = pd.DataFrame({
        "momentum": _roll_pct(mom),
        "trend": trend * 100,                         # already 0-100
        "breadth": _roll_pct(breadth),
        "low_volatility": 100 - _roll_pct(vol),       # high vol -> fear
        "strength": _roll_pct(dd),                    # near highs -> greed
    })
    return comp.dropna(how="all")


def mood_index(min_adv: float = config.MIN_ADV) -> pd.Series:
    comp = mood_components(min_adv)
    return comp.mean(axis=1).dropna().rename("mood")


def label_for(score: float) -> str:
    for lo, hi, lab in BANDS:
        if score < hi or hi == 100:
            if score >= lo:
                return lab
    return "Neutral"


def current_mood(min_adv: float = config.MIN_ADV) -> dict:
    mi = mood_index(min_adv)
    comp = mood_components(min_adv)
    score = float(mi.iloc[-1])
    prev = float(mi.iloc[-6]) if len(mi) > 6 else score
    return {
        "as_of": str(mi.index[-1].date()),
        "score": round(score, 1),
        "label": label_for(score),
        "week_ago": round(prev, 1),
        "components": {k: round(float(comp[k].iloc[-1]), 0) for k in comp.columns},
        "history": {"x": [str(d.date()) for d in mi.index[-260:]],
                    "y": [round(float(v), 1) for v in mi.values[-260:]]},
    }


def mood_backtest(fwd: int = 20, min_adv: float = config.MIN_ADV) -> dict:
    """HONEST test: forward `fwd`-day index return conditioned on the mood band
    at entry. If the gauge had contrarian value, Extreme Fear would show the
    highest forward return. In-sample & descriptive — reported as-is, not fitted.
    """
    mkt = data.market_index(min_adv)
    mi = mood_index(min_adv).reindex(mkt.index).ffill()
    loglvl = np.log1p(mkt).cumsum()
    fwd_ret = np.expm1(loglvl.shift(-fwd) - loglvl)      # forward fwd-day return
    df = pd.DataFrame({"mood": mi, "fwd": fwd_ret}).dropna()
    df["band"] = pd.cut(df.mood, [0, 20, 40, 60, 80, 100],
                        labels=[b[2] for b in BANDS], include_lowest=True)
    g = df.groupby("band", observed=True)["fwd"]
    tab = pd.DataFrame({"n": g.size(), "avg_fwd": g.mean().round(4),
                        "median_fwd": g.median().round(4),
                        "up_rate": g.apply(lambda s: round((s > 0).mean(), 3))})
    # monotonicity check: is fear rewarded more than greed?
    order = [b[2] for b in BANDS]
    avail = [b for b in order if b in tab.index]
    fear_end = tab.loc[avail[0], "avg_fwd"] if avail else np.nan
    greed_end = tab.loc[avail[-1], "avg_fwd"] if avail else np.nan
    verdict = ("weak contrarian signal: fear bands show higher forward returns"
               if fear_end > greed_end + 0.005 else
               "no reliable contrarian edge in-sample (fear not rewarded over greed)")
    return {"fwd_days": fwd, "table": tab.reset_index().to_dict(orient="records"),
            "verdict": verdict,
            "caveat": ("In-sample, ~%d days, one macro cycle. This describes the "
                       "historical relationship; it is NOT a fitted or forward-"
                       "validated predictor. A 'perfect backtest' here would be "
                       "curve-fitting." % len(df))}


if __name__ == "__main__":
    import json
    print("=== CURRENT MOOD ===")
    cm = current_mood()
    print(f"{cm['label']} — {cm['score']}/100 (was {cm['week_ago']} a week ago)")
    print("components:", cm["components"])
    print("\n=== HONEST MOOD BACKTEST (fwd 20d index return by band) ===")
    bt = mood_backtest(20)
    for r in bt["table"]:
        print(f"  {r['band']:>14}: n={r['n']:>4}  avg={r['avg_fwd']:+.3f}  "
              f"med={r['median_fwd']:+.3f}  up={r['up_rate']:.0%}")
    print("verdict:", bt["verdict"])
    print("caveat:", bt["caveat"])
