"""Central paths and constants for the Pakistan macro-financial terminal.

This project is a SEPARATE, standalone project that sits *on top of* the
`psx-quant` project (a sibling folder). It consumes psx-quant's cleaned PSX
daily data READ-ONLY and never modifies it. A snapshot of that data is copied
into data/vendor/ so the terminal is self-contained and reproducible.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA = ROOT / "data"
VENDOR = DATA / "vendor"
VENDOR_PARQUET = VENDOR / "psx_daily.parquet"   # read-only snapshot from psx-quant
MACRO_DIR = DATA / "macro"                       # curated + fetched macro series
KNOWLEDGE_DIR = ROOT / "knowledge"               # curated sector supply-chain graph
EVENTS_FILE = DATA / "events.json"               # dated policy/macro event catalog
NEWS_DIR = DATA / "news"                          # news items + 5-tier sentiment
REPORTS = ROOT / "reports"
TERMINAL_DIR = ROOT / "terminal"

# The sibling psx-quant project (source of the price snapshot + the timing edge).
# Only ever read from here; never write.
PSX_QUANT = ROOT.parent / "psx-quant"

# --- analytics constants (kept consistent with psx-quant so the market-timing
#     edge reproduces exactly) ---
START = "2019-08-01"          # first date used for index/regime analytics
MIN_ADV = 5e6                 # PKR: "liquid" threshold for the equal-weight index
PPY = 248                     # PSX trading days per year (matches psx-quant)
CASH_ANNUAL = 0.12            # realistic PKR T-bill yield for out-of-market capital

for _d in (MACRO_DIR, KNOWLEDGE_DIR, NEWS_DIR, REPORTS, TERMINAL_DIR):
    _d.mkdir(parents=True, exist_ok=True)
