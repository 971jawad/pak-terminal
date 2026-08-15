"""Refresh the terminal's inputs.

1) PSX prices: re-copy the read-only snapshot from the sibling psx-quant project
   (which has its own resilient dps.psx.com.pk downloader + daily GitHub Action).
   We never fetch PSX here or modify psx-quant — we just mirror its parquet.

2) Macro/global series: attempt live fetch from SBP EasyData and stooq. Both are
   bot-walled to plain requests in many environments (SBP -> 403, stooq -> JS
   proof-of-work), so this DEGRADES GRACEFULLY: on failure it keeps the committed
   seed and prints how to refresh from a browser-capable environment. Values that
   DO come through are written to data/macro/ with provenance.

Run: python -m scripts.refresh  [--prices] [--macro]
"""
from __future__ import annotations

import argparse
import shutil

import requests

from pakterm import config

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

STOOQ = "https://stooq.com/q/d/l/?s={sym}&i=d"   # usdpkr, cb.f (Brent), ^kse (KSE)
SBP_EASYDATA = "https://easydata.sbp.org.pk"      # requires portal/API access


def refresh_prices() -> None:
    src = config.PSX_QUANT / "data" / "psx_daily.parquet"
    if src.exists():
        config.VENDOR_PARQUET.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, config.VENDOR_PARQUET)
        print(f"[prices] mirrored snapshot from psx-quant "
              f"({config.VENDOR_PARQUET.stat().st_size/1e6:.1f} MB)")
    else:
        print(f"[prices] psx-quant snapshot not found at {src}; keeping existing "
              f"vendor parquet. (In psx-quant: run `python predict.py` to refresh.)")


def _try_stooq(sym: str) -> str | None:
    try:
        r = requests.get(STOOQ.format(sym=sym), headers={"User-Agent": UA}, timeout=20)
        if r.status_code == 200 and r.text[:4].lower() == "date":
            return r.text
    except requests.RequestException:
        pass
    return None


def refresh_macro() -> None:
    print("[macro] attempting live fetch (best-effort; sources are often bot-walled)")
    got = {}
    for name, sym in (("PKR/USD", "usdpkr"), ("Brent", "cb.f"), ("KSE-100", "^kse")):
        csv = _try_stooq(sym)
        if csv:
            (config.MACRO_DIR / f"raw_{sym.strip('^.')}.csv").write_text(csv, encoding="utf-8")
            got[name] = len(csv.splitlines()) - 1
    if got:
        print(f"[macro] stooq OK: {got} -> raw_*.csv written (merge into macro_monthly.csv)")
    else:
        print("[macro] stooq blocked (JS proof-of-work). Keeping committed seed.\n"
              "        To refresh: open stooq.com CSV links in a browser, or use the\n"
              "        in-app browser tool, then update data/macro/macro_monthly.csv.")
    # SBP EasyData reachability probe (informational only)
    try:
        code = requests.get(SBP_EASYDATA, headers={"User-Agent": UA}, timeout=15).status_code
    except requests.RequestException:
        code = "unreachable"
    print(f"[macro] SBP EasyData probe -> {code} "
          f"(policy rate, reserves, remittances, CA; portal access needed for API)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", action="store_true")
    ap.add_argument("--macro", action="store_true")
    a = ap.parse_args()
    if not (a.prices or a.macro):
        a.prices = a.macro = True
    if a.prices:
        refresh_prices()
    if a.macro:
        refresh_macro()


if __name__ == "__main__":
    main()
