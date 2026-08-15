"""FIPI / LIPI investor-flow signal (NCCPL "smart money" data).

What this is, honestly:
  * NCCPL publishes daily net buy/sell by INVESTOR CATEGORY at the MARKET level
    (Foreign, Banks/DFI, Mutual Funds, Individuals, Insurance, Companies, ...).
    It is NOT per-stock, so it is a TIMING / positioning signal, not a stock-
    selection feature — which is exactly where PSX's real edge lives anyway.
  * We currently hold the RECENT (~2-month) daily series + the latest week's
    client-type breakdown, extracted in-browser from finhisaab's NCCPL feed.
    A full multi-year history (needed to backtest flows) requires the NCCPL bulk
    portal (nccpl.com.pk) — a documented follow-up, see fetch_note().

So this module surfaces the CURRENT foreign/local positioning (real, useful for
context) and does not claim a backtested flow edge it hasn't earned.
"""
from __future__ import annotations

import json

from pakterm import config

FOREIGN = {"FOREIGN CORPORATES", "FOREIGN INDIVIDUAL"}


def load_flows() -> dict:
    f = config.DATA / "flows.json"
    if not f.exists():
        return {}
    return json.loads(f.read_text(encoding="utf-8"))


def summary() -> dict:
    d = load_flows()
    if not d:
        return {"available": False}
    fipi = d["daily"]["fipi"]; lipi = d["daily"]["lipi"]; days = d["daily"]["days"]
    last5 = sum(fipi[-5:])
    cum = sum(fipi)
    cw = d.get("client_week", {}).get("net_usd", {})
    ranked = sorted(cw.items(), key=lambda kv: -kv[1])
    return {
        "available": True, "as_of": d.get("as_of"), "source": d.get("source"),
        "coverage": d.get("coverage"),
        "fipi_last_usd_m": round(fipi[-1] / 1e6, 2),
        "fipi_5d_usd_m": round(last5 / 1e6, 2),
        "fipi_cum_usd_m": round(cum / 1e6, 1),
        "foreign_stance": ("net BUYER" if last5 > 0 else "net SELLER"),
        "top_buyer": ranked[0][0] if ranked else None,
        "top_seller": ranked[-1][0] if ranked else None,
        "client_week": cw,
        "series": {"days": days,
                   "fipi_m": [round(v / 1e6, 3) for v in fipi],
                   "lipi_m": [round(v / 1e6, 3) for v in lipi]},
    }


def fetch_note() -> str:
    return ("Refresh: NCCPL publishes FIPI/LIPI daily ~18:00 PKT. Recent data can "
            "be pulled from finhisaab.com (Next.js RSC payload) or sarmaaya.pk; "
            "full history needs NCCPL's downloads portal (nccpl.com.pk/downloads). "
            "Per-stock foreign flow is not public — market/sector level only.")


if __name__ == "__main__":
    s = summary()
    if not s.get("available"):
        print("no flows data")
    else:
        print(f"FIPI as of {s['as_of']}: last {s['fipi_last_usd_m']}M, 5d {s['fipi_5d_usd_m']}M, "
              f"cum(2mo) {s['fipi_cum_usd_m']}M -> foreign {s['foreign_stance']}")
        print(f"this week — top buyer: {s['top_buyer']}, top seller: {s['top_seller']}")
