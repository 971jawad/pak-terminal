"""Self-contained PSX data pipeline for pak-terminal (no dependency on psx-quant).

Downloads new dps.psx.com.pk daily files into data/raw/ (resume-safe; historical
files are committed so CI only fetches the 1-2 new days), then parses all of
data/raw/ into data/vendor/psx_daily.parquet — the snapshot the terminal reads.

Run: python -m scripts.fetch_psx
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import gzip
import json
import sys
import threading
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "vendor" / "psx_daily.parquet"
HOLIDAYS = ROOT / "data" / "holidays.json"
BASE = "https://dps.psx.com.pk/download/mkt_summary/{}.Z"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
START = dt.date(2019, 7, 1)
WORKERS, RETRIES = 8, 3
# The newest file is what the deployed terminal is judged on. A transient 403
# from DPS rate-limiting cost psx-quant its 2026-09-04 file (fail=1, silent),
# so recent dates get materially more patience than historical backfill.
RECENT_DAYS, RECENT_RETRIES = 7, 6
COLS = ["date", "symbol", "sector", "name", "open", "high", "low", "close", "volume", "ldcp"]
_tls = threading.local()


def _session():
    if not hasattr(_tls, "s"):
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Accept": "*/*",
                          "Referer": "https://dps.psx.com.pk/downloads"})
        _tls.s = s
    return _tls.s


def _fetch(date: dt.date) -> str:
    url = BASE.format(date.isoformat()); out = RAW / f"{date.isoformat()}.Z"
    recent = (dt.date.today() - date).days <= RECENT_DAYS
    for attempt in range(RECENT_RETRIES if recent else RETRIES):
        try:
            r = _session().get(url, timeout=30)
            if r.status_code == 404:
                return "holiday"
            if r.status_code == 200 and r.content[:2] in (b"PK", b"\x1f\x8b"):
                out.write_bytes(r.content); return "ok"
        except requests.RequestException:
            pass
        time.sleep(min(2.5 * (attempt + 1) if recent else 1.5 * (attempt + 1), 20.0))
    return "fail"


def download() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    holidays = set(json.loads(HOLIDAYS.read_text())) if HOLIDAYS.exists() else set()
    have = {p.stem for p in RAW.glob("*.Z")}
    d, dates = START, []
    end = dt.date.today()
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in have and d.isoformat() not in holidays:
            dates.append(d)
        d += dt.timedelta(days=1)
    print(f"[fetch] queue={len(dates)} have={len(have)}", flush=True)
    stats = {"ok": 0, "holiday": 0, "fail": 0, "pending": 0}
    today = dt.date.today()
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(_fetch, dd): dd for dd in dates}
        for fut in cf.as_completed(futs):
            res = fut.result(); d = futs[fut]
            if res == "holiday" and d >= today:
                # A 404 for TODAY usually means "PSX has not published yet"
                # (close is 15:30 PKT), NOT "market closed". Recording it would
                # brand a real session a permanent holiday -- it is never
                # re-probed -- and, now that holidays drive period finality,
                # could close a period early. Leave it for tomorrow's run.
                stats["pending"] += 1
                continue
            stats[res] += 1
            if res == "holiday":
                holidays.add(d.isoformat())
    HOLIDAYS.write_text(json.dumps(sorted(holidays), indent=0))
    print(f"[fetch] {stats}", flush=True)
    if stats["fail"]:
        # a hard fail is NOT a holiday: the date stays queued and is retried next
        # run, but say so loudly so a stale site is never mistaken for a closed market
        print(f"[fetch] WARNING: {stats['fail']} date(s) hard-failed (403/5xx/timeout, "
              f"not a 404 holiday). They remain queued for the next run.", flush=True)


def _parse_file(path: Path) -> list[list]:
    try:
        blob = path.read_bytes()
        if blob[:2] == b"\x1f\x8b":
            text = gzip.decompress(blob).decode("utf-8", errors="replace")
        else:
            with zipfile.ZipFile(path) as zf:
                member = next(n for n in zf.namelist() if n.lower().endswith(".lis"))
                text = zf.read(member).decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, gzip.BadGzipFile, StopIteration):
        return []
    return [ln.split("|")[:10] for ln in text.splitlines() if len(ln.split("|")) >= 10]


def parse() -> None:
    files = sorted(RAW.glob("*.Z"))
    print(f"[parse] {len(files)} files", flush=True)
    rows = []
    for f in files:
        rows.extend(_parse_file(f))
    df = pd.DataFrame(rows, columns=COLS)
    df["date"] = pd.to_datetime(df["date"], format="%d%b%Y")
    for c in ["open", "high", "low", "close", "ldcp"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")
    for c in ("symbol", "name", "sector"):
        df[c] = df[c].str.strip()
    df = df.dropna(subset=["close"]); df = df[df["close"] > 0]
    df = df.drop_duplicates(subset=["date", "symbol"], keep="last")
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"[parse] wrote {OUT} rows={len(df):,} through {df.date.max().date()}", flush=True)


if __name__ == "__main__":
    if "--no-fetch" not in sys.argv:
        download()
    parse()
