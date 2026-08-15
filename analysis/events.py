"""Event studies: how PSX sectors historically moved around dated policy/macro
events. Descriptive decision-support, NOT a fitted predictor.

Abnormal return = sector equal-weight daily return minus the equal-weight liquid
market return (a simple market model, intercept 0, beta 1 — robust for EW sector
baskets on a short sample). We report cumulative abnormal return (CAR) over event
windows and aggregate by event *type*, with the sample size, because any single
event is N=1 and only categories carry (weak) statistical weight.
"""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from pakterm import config, data


def load_events() -> pd.DataFrame:
    if not config.EVENTS_FILE.exists():
        return pd.DataFrame(columns=["date", "type", "title", "sectors",
                                     "expected_sign", "source", "confidence"])
    obj = json.loads(config.EVENTS_FILE.read_text(encoding="utf-8"))
    ev = pd.DataFrame(obj.get("events", []))
    if not ev.empty:
        ev["date"] = pd.to_datetime(ev["date"])
        ev = ev.sort_values("date").reset_index(drop=True)
    return ev


@lru_cache(maxsize=4)
def _abnormal(min_adv: float = config.MIN_ADV) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    sec = data.sector_daily_returns(min_adv)
    mkt = data.market_index(min_adv)
    abn = sec.sub(mkt, axis=0)          # sector minus market, per day
    return abn, abn.index


def _nearest_idx(days: pd.DatetimeIndex, d: pd.Timestamp) -> int | None:
    pos = days.searchsorted(d)
    if pos >= len(days):
        return None
    return int(pos)


def car(sector: str, event_date: pd.Timestamp, lo: int, hi: int,
        min_adv: float = config.MIN_ADV) -> float | None:
    """Cumulative abnormal return for `sector` over trading-day window [lo,hi]
    relative to the first trading day on/after event_date (offset 0)."""
    abn, days = _abnormal(min_adv)
    if sector not in abn.columns:
        return None
    i = _nearest_idx(days, event_date)
    if i is None or i + lo < 0 or i + hi >= len(days):
        return None
    seg = abn[sector].iloc[i + lo: i + hi + 1]
    return float(seg.sum())


WINDOWS = {"pre[-5,-1]": (-5, -1), "event[0,1]": (0, 1),
           "post[1,5]": (1, 5), "drift[1,20]": (1, 20)}


def event_study(min_adv: float = config.MIN_ADV) -> pd.DataFrame:
    """Per-event CAR for each named sector, across the standard windows."""
    ev = load_events()
    if ev.empty:
        return pd.DataFrame()
    rows = []
    for e in ev.itertuples():
        secs = e.sectors if isinstance(e.sectors, list) else []
        for s in secs:
            row = {"date": e.date.date(), "type": e.type, "title": e.title,
                   "sector": s, "expected_sign": getattr(e, "expected_sign", None)}
            for wname, (lo, hi) in WINDOWS.items():
                row[wname] = car(s, e.date, lo, hi, min_adv)
            rows.append(row)
    return pd.DataFrame(rows)


def by_type(min_adv: float = config.MIN_ADV) -> pd.DataFrame:
    """Average CAR by event type x window, with n. The honest headline output."""
    es = event_study(min_adv)
    if es.empty:
        return pd.DataFrame()
    wins = list(WINDOWS)
    agg = es.groupby("type")[wins].agg(["mean", "count"])
    # flatten + keep a single n (same across windows within a type mostly)
    out = pd.DataFrame(index=agg.index)
    for w in wins:
        out[w] = agg[(w, "mean")].round(4)
    out["n"] = es.groupby("type")["event[0,1]"].count()
    return out.sort_values("n", ascending=False)


def hit_rate(min_adv: float = config.MIN_ADV) -> pd.DataFrame:
    """Did the event[0,1] CAR match the analyst's expected_sign? By type."""
    es = event_study(min_adv)
    if es.empty:
        return pd.DataFrame()
    es = es.dropna(subset=["event[0,1]", "expected_sign"])
    es = es[es["expected_sign"] != 0]
    es["correct"] = np.sign(es["event[0,1]"]) == np.sign(es["expected_sign"])
    g = es.groupby("type")["correct"]
    return pd.DataFrame({"hit_rate": g.mean().round(2), "n": g.count()}) \
        .sort_values("n", ascending=False)


if __name__ == "__main__":
    bt = by_type()
    if bt.empty:
        print("(event catalog not seeded yet -> event study empty)")
    else:
        print("=== average sector abnormal return (CAR) by event type ===")
        print(bt.to_string())
        print("\n=== expected-sign hit rate by type ===")
        print(hit_rate().to_string())
