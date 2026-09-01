"""PSX trading-calendar finality — the ONLY place that decides whether a
period (week/month) can still gain another session.

WHY: picks used to resolve/roll only once a LATER period appeared in the data
("wait for a September day before closing August"). That is pure latency: once we
hold 2026-08-31, the calendar already proves no August session can follow. This
module answers "can this period still gain a session?" from the calendar instead.

Facts this rests on, verified over 2019-07-01..2026-08-31 (1,773 sessions):
  * PSX trades Mon-Fri. Zero weekend rows in 7 years; zero weekend holiday entries.
  * holidays.json is populated REACTIVELY (a date is recorded only after a 404,
    and the fetcher never probes past today). It knows NOTHING about the future,
    so any weekday past what the fetcher probed is UNKNOWN and must force a WAIT.
  * A falsely recorded holiday is never re-probed, so the file's self-consistency
    proves COMPLETENESS, not CORRECTNESS -> hence QUARANTINE_DAYS below.

Safety properties (point-in-time replay, 2019-2026, all configs incl. empty and
stale holiday files): ZERO premature finality for W and M; historical exit dates
byte-identical to the legacy rule.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

# Distrust a 404-discovered holiday until it is this many days older than the
# newest date the fetcher demonstrably probed. A same-day 404 can mean
# "PSX has not published yet", not "market closed" — exactly how 2026-09-01 got
# written to this repo's holidays.json by an 11:04 PKT run (close is 15:30).
QUARANTINE_DAYS = 1


@lru_cache(maxsize=8)
def load_holidays(path: str | Path) -> frozenset:
    """Weekday holiday dates from data/holidays.json. Weekend entries dropped."""
    p = Path(path)
    if not p.exists():
        return frozenset()
    try:
        raw = json.loads(p.read_text())
    except Exception:
        return frozenset()
    out = set()
    for s in raw:
        try:
            d = pd.Timestamp(s).normalize()
        except Exception:
            continue
        if d.weekday() < 5:              # a weekend entry is meaningless here
            out.add(d)
    return frozenset(out)


def probed_through(latest: pd.Timestamp, holidays) -> pd.Timestamp:
    """Lower bound on the last date the fetcher actually probed.

    `latest` (newest session) and max(holidays) are both written ONLY by the
    fetcher, so their max is a date it provably reached. A LOWER bound is the
    safe side: it marks MORE days unknown, never fewer.

    NEVER substitute Timestamp.today(): that asserts the fetcher ran when it may
    not have. If data is 15 days stale, a clock-anchored bound would wrongly
    declare the month final off an old close.
    """
    latest = pd.Timestamp(latest).normalize()
    return max([latest] + ([max(holidays)] if holidays else []))


def period_is_final(target: pd.Period,
                    latest: pd.Timestamp,
                    holidays=frozenset(),
                    probed: pd.Timestamp | None = None,
                    quarantine_days: int = QUARANTINE_DAYS) -> bool:
    """True iff NO possible trading day remains in `target` after `latest`.

    target : pd.Period, freq 'M' or 'W-SUN' (pandas 'W' == 'W-SUN', ISO-aligned;
             written explicitly because CI installs pandas unpinned).
    latest : newest OBSERVED trading date (all_days.max() / data.latest_date()).
             Never the wall clock.

    The `lp > target` branch is the LEGACY rule kept verbatim as a liveness
    fallback: without it, one real session missing from the panel but absent from
    holidays.json would block its period forever. With it, the worst case
    degrades exactly to the old behaviour — this can never be worse than before.
    """
    latest = pd.Timestamp(latest).normalize()
    lp = latest.to_period(target.freqstr)
    if lp > target:
        return True                      # a later period exists -> legacy rule
    if lp < target:
        return False                     # data has not reached the period yet

    if probed is None:
        probed = probed_through(latest, holidays)
    cutoff = pd.Timestamp(probed).normalize() - pd.Timedelta(days=quarantine_days)

    day = latest + pd.Timedelta(days=1)
    end = target.end_time.normalize()
    while day <= end:
        weekend = day.weekday() >= 5
        known_holiday = (day in holidays) and (day <= cutoff)
        if not (weekend or known_holiday):
            return False                 # a possible trading day remains -> WAIT
        day += pd.Timedelta(days=1)
    return True


def psx_holidays() -> frozenset:
    """The repo's holiday set (cached). Convenience so call sites stay two lines."""
    from pakterm import config
    return load_holidays(config.DATA / "holidays.json")


def last_final_period(periods, latest, holidays=frozenset(), **kw):
    """Newest period in `periods` that is final; None if none is."""
    fin = [p for p in sorted(periods)
           if period_is_final(p, latest, holidays, **kw)]
    return fin[-1] if fin else None
