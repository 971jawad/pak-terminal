"""PSX price adapter + macro-series loader — the data contract every analytics
module builds on.

Design notes:
  * Prices come from the read-only psx-quant snapshot (data/vendor/psx_daily.parquet).
  * Cleaning + the equal-weight liquid index reproduce psx-quant exactly, so the
    verified market-timing edge (Sharpe ~1.15 -> ~1.45, DD halved) carries over.
  * Macro series are loaded from data/macro/*.csv (curated, sourced, refreshable).
    Missing files degrade to empty frames rather than crashing.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from . import config
from .sectors import sector_name, is_equity_sector

# ------------------------------------------------------------------ prices

@lru_cache(maxsize=1)
def load_prices() -> pd.DataFrame:
    """Cleaned per-symbol daily panel with returns, liquidity, sector names.

    Mirrors psx-quant's cleaning (drop futures/rights/debt) and its adjusted
    daily return r1 = close/ldcp - 1, so the index and timing edge match.
    """
    df = pd.read_parquet(config.VENDOR_PARQUET)
    df["name"] = df["name"].astype(str)
    df["sector"] = df["sector"].astype(str).str.strip()

    # drop non-equity lines (same rules as psx-quant/research/core.py)
    df = df[~df.symbol.str.contains("-", regex=False)]
    rights = (df.symbol.str.match(r".*R[0-9]$")
              | (df.symbol.str.match(r".*R[0-9]?$") & df.name.str.contains(r"\(R", regex=True)))
    df = df[~rights]
    debt = (df.symbol.str.match(r"^P\d{2}") | df.symbol.str.contains("TFC")
            | df.symbol.str.contains("SUK"))
    df = df[~debt]
    df = df[df.ldcp > 0]
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    df["r1"] = (df.close / df.ldcp - 1).clip(-0.9, 4.0)
    df["logr"] = np.log1p(df.r1)
    g = df.groupby("symbol", sort=False)
    df["cumlog"] = g["logr"].cumsum()
    df["value"] = df.close * df.volume
    df["adv_20"] = g["value"].transform(lambda s: s.rolling(20, min_periods=5).median())

    df["sector_name"] = df.sector.map(sector_name)
    df["is_equity"] = df.sector.map(is_equity_sector)
    return df


def latest_date() -> pd.Timestamp:
    return load_prices().date.max()


# ------------------------------------------------------------------ indices

def liquid_mask(df: pd.DataFrame, min_adv: float = config.MIN_ADV) -> pd.Series:
    return (df.adv_20 > min_adv) & (df.volume > 0)


@lru_cache(maxsize=8)
def market_index(min_adv: float = config.MIN_ADV, start: str = config.START) -> pd.Series:
    """Equal-weight daily return of the liquid universe (matches psx-quant)."""
    df = load_prices()
    liq = df[df.adv_20 > min_adv]
    mkt = liq.groupby("date")["r1"].mean().sort_index()
    return mkt[mkt.index >= start]


def market_breadth(min_adv: float = config.MIN_ADV, start: str = config.START) -> pd.Series:
    df = load_prices()
    liq = df[df.adv_20 > min_adv]
    b = liq.groupby("date")["r1"].apply(lambda s: (s > 0).mean()).sort_index()
    return b[b.index >= start]


@lru_cache(maxsize=8)
def sector_daily_returns(min_adv: float = config.MIN_ADV,
                         start: str = config.START) -> pd.DataFrame:
    """date x sector_name equal-weight daily returns for liquid equity names."""
    df = load_prices()
    liq = df[(df.adv_20 > min_adv) & df.is_equity]
    sr = (liq.groupby(["date", "sector_name"])["r1"].mean()
          .unstack("sector_name").sort_index())
    return sr[sr.index >= start]


def to_monthly_returns(daily: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Compound daily simple returns into calendar-month returns."""
    logd = np.log1p(daily)
    m = logd.groupby(logd.index.to_period("M")).sum()
    return np.expm1(m)


# ------------------------------------------------------------------ macro

# Canonical monthly macro schema. Columns are optional; whatever the curated /
# fetched CSV provides is returned. Units documented in data/macro/README.md.
MACRO_COLUMNS = [
    "policy_rate",          # SBP policy (target) rate, % (month-end)
    "cpi_yoy",              # headline CPI inflation, % YoY
    "fx_reserves_sbp_bn",   # SBP-held FX reserves, USD bn (month-end)
    "remittances_bn",       # workers' remittances, USD bn (monthly inflow)
    "current_account_mn",   # current account balance, USD mn (monthly, +surplus)
    "trade_balance_mn",     # goods trade balance, USD mn (monthly)
    "pkr_usd",              # PKR per USD (interbank, month-end)
    "brent_usd",            # Brent crude, USD/bbl (month avg)
    "kse100",               # KSE-100 index level (month-end)
    "us_10y",               # US 10y treasury yield, % (month-end)
    "m2_growth_yoy",        # broad money growth, % YoY
]


def load_macro_monthly() -> pd.DataFrame:
    """Monthly macro panel indexed by month-end Timestamp. Empty if not seeded."""
    f = config.MACRO_DIR / "macro_monthly.csv"
    if not f.exists():
        return pd.DataFrame(columns=MACRO_COLUMNS)
    m = pd.read_csv(f)
    m["date"] = pd.to_datetime(m["date"])
    m = m.set_index("date").sort_index()
    return m


def load_policy_rate_events() -> pd.DataFrame:
    """Dated SBP policy-rate decisions: columns [date, rate, change_bps, source]."""
    f = config.MACRO_DIR / "policy_rate.csv"
    if not f.exists():
        return pd.DataFrame(columns=["date", "rate", "change_bps", "source"])
    e = pd.read_csv(f)
    e["date"] = pd.to_datetime(e["date"])
    return e.sort_values("date").reset_index(drop=True)


# ------------------------------------------------------------------ futures eligibility

_MONTHS3 = {"JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"}
_INDEX_FUT = {"KSE30", "KMI30", "BKTI", "KSE100", "ALLSHR", "KMIALLSHR"}


@lru_cache(maxsize=1)
def futures_contracts() -> pd.DataFrame:
    """Single-stock deliverable-futures rows (SYMBOL-MMM) from the raw file —
    these are dropped by load_prices() but reveal the ACTUAL futures-eligible
    universe, point-in-time. Returns [date, base] (base = underlying ticker)."""
    raw = pd.read_parquet(config.VENDOR_PARQUET, columns=["date", "symbol"])
    raw["symbol"] = raw["symbol"].astype(str)
    f = raw[raw.symbol.str.contains("-", regex=False)].copy()
    f["suf"] = f.symbol.str.split("-").str[-1].str.upper()
    f = f[f.suf.isin(_MONTHS3)]
    f["base"] = f.symbol.str.split("-").str[0]
    f = f[~f.base.isin(_INDEX_FUT) & ~f.base.str.contains("ETF")]
    return f[["date", "base"]].reset_index(drop=True)


@lru_cache(maxsize=1)
def futures_eligible_months() -> pd.DataFrame:
    """Distinct (base ticker, month) pairs in which a futures contract traded."""
    f = futures_contracts().copy()
    f["ym"] = f.date.dt.to_period("M")
    return f[["base", "ym"]].drop_duplicates().reset_index(drop=True)


def eligible_now(days: int = 60) -> list[str]:
    f = futures_contracts()
    cut = f.date.max() - pd.Timedelta(days=days)
    return sorted(f[f.date >= cut].base.unique())


def policy_rate_series(index: pd.DatetimeIndex) -> pd.Series:
    """Step-function policy rate reindexed (ffill) onto any date index."""
    ev = load_policy_rate_events()
    if ev.empty:
        return pd.Series(index=index, dtype=float)
    s = ev.set_index("date")["rate"].sort_index()
    s = s[~s.index.duplicated(keep="last")]           # guard duplicate decision dates
    index = pd.DatetimeIndex(index)
    full = s.index.union(index)
    full = full[~full.duplicated()]
    return s.reindex(full).ffill().reindex(index)
