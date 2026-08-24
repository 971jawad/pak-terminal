"""Live PSX catalyst feed — scrapes the official announcements portal
(dps.psx.com.pk) for recent material announcements and classifies them.

A SEPARATE, additive component. The scrape recipe (POST /announcements with
type=C) is the one that works headlessly — no captcha, just the right payload.
Used for the terminal's "Today's catalysts" panel; runs in the daily CI.

This is AWARENESS, not a drift signal — the honest PEAD backtest showed no
tradeable post-announcement drift on next-day entry. It tells you WHAT was
announced, so a human can judge; it does not claim an edge.
"""
from __future__ import annotations

import re
import time

BASE = "https://dps.psx.com.pk"
_ROW = re.compile(
    r"<tr>\s*<td>([A-Z][a-z]{2} \d{1,2}, \d{4})</td>\s*<td>([^<]*)</td>\s*"
    r"<td><a[^>]*href=\"/company/([^\"]+)\"[^>]*>.*?</td>\s*<td>.*?</td>\s*<td>([^<]*)</td>", re.S)
_TOT = re.compile(r"of ([0-9]+) entries")

# title-keyword -> catalyst class (checked in order; first match wins)
_RULES = [
    ("EARNINGS", r"financial result|quarter ended|year ended|half year|profit|accounts for"),
    ("DIVIDEND", r"dividend|payout|book closure|entitlement"),
    ("RIGHTS/BONUS", r"right issue|bonus|share split"),
    ("CORP-ACTION", r"acquisi|merger|expansion|commission|production|contract|agreement|plant|capacity|investment|joint venture|de-?merger"),
    ("RATING", r"rating|credit rating|entity rating"),
    ("GOVERNANCE", r"appointment|resignation|ceo|director|chairman|chief executive"),
    ("MEETING", r"board meeting|agm|egm|general meeting|briefing|closed period"),
]


def _classify(title: str) -> str:
    t = title.lower()
    for cls, pat in _RULES:
        if re.search(pat, t):
            return cls
    return "OTHER"


def _session():
    import requests
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": f"{BASE}/announcements/companies", "Origin": BASE})
    try:
        s.get(f"{BASE}/announcements/companies", timeout=20)   # session cookie
    except Exception:
        pass
    return s


def fetch_range(date_from: str, date_to: str, query: str = "", max_pages: int = 60) -> list[dict]:
    """Pull all category-C announcements in [date_from, date_to] (YYYY-MM-DD)."""
    s = _session()
    out, off, total = [], 0, None
    for _ in range(max_pages):
        try:
            r = s.post(f"{BASE}/announcements", timeout=25, data={
                "type": "C", "symbol": "", "query": query, "count": 50, "offset": off,
                "date_from": date_from, "date_to": date_to, "page": "annc"})
        except Exception:
            break
        if r.status_code != 200:
            break
        html = r.text
        if total is None:
            m = _TOT.search(html); total = int(m.group(1)) if m else 0
        rows = _ROW.findall(html)
        for d, tm, sym, title in rows:
            title = re.sub(r"\s+", " ", title).strip()
            out.append({"date": d, "time": tm.strip(), "symbol": sym,
                        "title": title[:120], "type": _classify(title)})
        off += 50
        if off >= (total or 0) or not rows:
            break
        time.sleep(0.15)
    return out


def catalyst_feed(days: int = 30, eligible: set | None = None) -> dict:
    """Recent catalysts for the terminal. `eligible` = set of futures-eligible
    symbols to flag with ⚡. Dates come as 'Mon DD, YYYY' strings from PSX."""
    from datetime import date, timedelta
    import pandas as pd
    today = date.today()
    frm = (today - timedelta(days=days)).isoformat()
    items = fetch_range(frm, today.isoformat())
    # de-dupe, sort newest first, keep the catalytic classes prominent
    seen, ded = set(), []
    for it in items:
        k = (it["date"], it["symbol"], it["title"][:40])
        if k in seen:
            continue
        seen.add(k)
        it["eligible"] = bool(eligible and it["symbol"] in eligible)
        ded.append(it)
    def _dt(s):
        try:
            return pd.to_datetime(s, format="%b %d, %Y")
        except Exception:
            return pd.NaT
    ded.sort(key=lambda x: (_dt(x["date"]), x["time"]), reverse=True)
    counts = {}
    for it in ded:
        counts[it["type"]] = counts.get(it["type"], 0) + 1
    KEY = {"EARNINGS", "DIVIDEND", "RIGHTS/BONUS", "CORP-ACTION", "RATING"}
    key_items = [it for it in ded if it["type"] in KEY][:60]
    return {"as_of": today.isoformat(), "window_days": days,
            "n_total": len(ded), "counts": counts, "items": key_items,
            "note": "Awareness feed of material PSX announcements (dps.psx.com.pk). "
                    "NOT a drift signal — post-announcement drift is not tradeable on "
                    "next-day entry (tested); this shows what was announced so you can judge."}


if __name__ == "__main__":
    r = catalyst_feed(days=14)
    print(f"catalyst feed as of {r['as_of']} — {r['n_total']} announcements, counts={r['counts']}\n")
    for it in r["items"][:25]:
        print(f"  {it['date']:13} {it['symbol']:10} {it['type']:12} {it['title'][:60]}")
