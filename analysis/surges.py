"""Surge, multi-bagger and sector-boom meta-analysis — mined from the price panel.

All of this is DESCRIPTIVE history (what happened), computed from 7 years of PSX
data. It includes an honest in-sample test of the user's thesis that banks boom
when interest rates are high (tested against the 2019-2026 rate cycle, which ran
7% -> 22% -> 11%, giving real variation).

Nothing here is a forward predictor: surge base-rates and boom conditions are
suggestive context, not tradable signals, and are labelled as such.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from pakterm import config, data


# ---------------------------------------------------------------- per-symbol

@lru_cache(maxsize=2)
def symbol_stats(min_adv: float = 3e6, min_price: float = 2.0) -> pd.DataFrame:
    """Full-history stats per symbol: total & peak multiple, CAGR, liquidity."""
    df = data.load_prices()
    rows = []
    for sym, g in df.groupby("symbol", sort=False):
        g = g.sort_values("date")
        if len(g) < 60:
            continue
        cum = g["cumlog"].to_numpy()
        mult = np.exp(cum - cum[0])            # cumulative multiple vs first close
        peak_mult = float(np.nanmax(mult))
        end_mult = float(mult[-1])
        adv = float(g["value"].rolling(20, min_periods=5).median().median())
        yrs = (g["date"].iloc[-1] - g["date"].iloc[0]).days / 365.25
        cagr = end_mult ** (1 / yrs) - 1 if yrs > 0.5 and end_mult > 0 else np.nan
        peak_i = int(np.nanargmax(mult))
        rows.append({
            "symbol": sym, "sector": data.sector_name(g["sector"].iloc[-1]),
            "name": str(g["name"].iloc[-1]), "start": g["date"].iloc[0].date(),
            "end": g["date"].iloc[-1].date(), "years": round(yrs, 1),
            "end_mult": round(end_mult, 2), "peak_mult": round(peak_mult, 2),
            "cagr": None if np.isnan(cagr) else round(float(cagr), 3),
            "peak_date": g["date"].iloc[peak_i].date(),
            "med_adv_pkr": adv, "last_close": float(g["close"].iloc[-1]),
        })
    s = pd.DataFrame(rows)
    return s[(s.med_adv_pkr >= min_adv) & (s.last_close >= min_price)].reset_index(drop=True)


def multibaggers(min_mult: float = 3.0, by: str = "peak_mult", top: int = 30,
                 min_years: float = 1.5) -> pd.DataFrame:
    s = symbol_stats()
    s = s[s.years >= min_years]      # drop recent-IPO spike artifacts (bogus CAGR)
    out = s[s[by] >= min_mult].sort_values(by, ascending=False)
    return out.head(top)[["symbol", "name", "sector", "end_mult", "peak_mult",
                          "cagr", "years", "peak_date"]]


def top_gainers_by_year(min_adv: float = 5e6, n: int = 5) -> pd.DataFrame:
    """Best liquid performers per calendar year (by within-year return)."""
    df = data.load_prices()
    df = df[df.adv_20 > min_adv].copy()
    df["year"] = df.date.dt.year
    rows = []
    for (yr, sym), g in df.groupby(["year", "symbol"], sort=False):
        g = g.sort_values("date")
        if len(g) < 100:
            continue
        r = float(np.exp(g["cumlog"].iloc[-1] - g["cumlog"].iloc[0]) - 1)
        rows.append({"year": yr, "symbol": sym, "name": str(g["name"].iloc[-1]),
                     "sector": data.sector_name(g["sector"].iloc[-1]), "ret": r})
    d = pd.DataFrame(rows)
    return (d.sort_values(["year", "ret"], ascending=[True, False])
            .groupby("year").head(n).reset_index(drop=True))


# ---------------------------------------------------------------- bank / rate thesis

def bank_rate_thesis() -> dict:
    """Test: do banks outperform when the policy-rate LEVEL is high? (2019-2026).

    Uses the rate LEVEL (not change). Reports absolute and market-excess bank
    returns, split by rate regime, plus correlation with t-stat, for the sector
    and for MEBL/UBL individually.
    """
    sec = data.sector_daily_returns()
    mkt = data.market_index()
    # monthly
    bank_m = data.to_monthly_returns(sec["Commercial Banks"]) if "Commercial Banks" in sec else pd.Series(dtype=float)
    mkt_m = data.to_monthly_returns(mkt)
    excess_m = bank_m - mkt_m
    # month-end policy rate level
    m_idx = bank_m.index.to_timestamp("M")
    rate = data.policy_rate_series(pd.DatetimeIndex(m_idx))
    rate.index = bank_m.index

    def corr_t(x, y):
        j = pd.concat([x, y], axis=1).dropna()
        n = len(j)
        if n < 8:
            return (np.nan, n, np.nan)
        r = j.iloc[:, 0].corr(j.iloc[:, 1])
        t = r * np.sqrt((n - 2) / max(1e-9, 1 - r * r))
        return (round(float(r), 3), n, round(float(t), 2))

    regimes = {"low (<10%)": rate < 10, "mid (10-15%)": (rate >= 10) & (rate < 15),
               "high (>=15%)": rate >= 15}
    split = {}
    for lbl, mask in regimes.items():
        split[lbl] = {"n_months": int(mask.sum()),
                      "bank_avg": round(float(bank_m[mask].mean()), 4) if mask.sum() else None,
                      "bank_excess_avg": round(float(excess_m[mask].mean()), 4) if mask.sum() else None,
                      "mkt_avg": round(float(mkt_m[mask].mean()), 4) if mask.sum() else None}

    # individual names (monthly return from cumlog)
    df = data.load_prices()
    indiv = {}
    for tk in ("MEBL", "UBL", "HBL", "MCB"):
        g = df[df.symbol == tk]
        if g.empty:
            continue
        cm = data.to_monthly_returns(
            np.expm1(g.set_index("date")["cumlog"].groupby(level=0).last().diff()))
        # simpler: monthly return of the symbol via cumlog month-end
        s = g.set_index("date")["cumlog"]
        mend = s.groupby(s.index.to_period("M")).last()
        rr = np.expm1(mend.diff())
        rr.index = mend.index
        ex = rr - mkt_m.reindex(rr.index)
        indiv[tk] = {"corr_level": corr_t(rate.reindex(rr.index), rr),
                     "excess_high": round(float(ex[rate.reindex(rr.index) >= 15].mean()), 4)
                     if (rate.reindex(rr.index) >= 15).sum() else None,
                     "excess_low": round(float(ex[rate.reindex(rr.index) < 10].mean()), 4)
                     if (rate.reindex(rr.index) < 10).sum() else None}

    return {
        "sector_corr_rate_level": corr_t(rate, bank_m),
        "sector_excess_corr_rate_level": corr_t(rate, excess_m),
        "regime_split": split,
        "individual": indiv,
        "verdict": _bank_verdict(split),
    }


def _bank_verdict(split: dict) -> str:
    hi = split.get("high (>=15%)", {}).get("bank_excess_avg")
    lo = split.get("low (<10%)", {}).get("bank_excess_avg")
    if hi is None or lo is None:
        return "insufficient regime coverage"
    if hi > lo + 0.005:
        return (f"SUPPORTED in-sample: banks' market-excess return averaged "
                f"{hi:+.1%}/mo in high-rate months vs {lo:+.1%}/mo in low-rate months.")
    if hi < lo - 0.005:
        return (f"NOT supported in-sample: banks' excess return was {hi:+.1%}/mo high-rate "
                f"vs {lo:+.1%}/mo low-rate (opposite of the thesis).")
    return f"MIXED: high-rate {hi:+.1%}/mo vs low-rate {lo:+.1%}/mo (no clear edge)."


# ---------------------------------------------------------------- surges

def surge_episodes(thresh: float = 0.5, window: int = 20, min_adv: float = 5e6) -> pd.DataFrame:
    """Episodes where a liquid stock rose >= `thresh` over <= `window` trading days.

    For each, records the sector, prior 20d momentum, and the FORWARD 20d return
    after the surge peak (does it continue or mean-revert?). Non-overlapping per
    symbol (skip `window` days after a detected surge).
    """
    df = data.load_prices()
    df = df[df.adv_20 > min_adv]
    rows = []
    for sym, g in df.groupby("symbol", sort=False):
        g = g.sort_values("date").reset_index(drop=True)
        cum = g["cumlog"].to_numpy()
        n = len(g)
        i = window
        while i < n:
            past = np.exp(cum[i] - cum[i - window]) - 1
            if past >= thresh:
                fwd = np.exp(cum[min(i + window, n - 1)] - cum[i]) - 1
                prior = np.exp(cum[i - window] - cum[max(i - 2 * window, 0)]) - 1
                rows.append({"symbol": sym, "sector": data.sector_name(g["sector"].iloc[i]),
                             "date": g["date"].iloc[i].date(), "surge": round(float(past), 3),
                             "prior_mom": round(float(prior), 3),
                             "fwd_20d": round(float(fwd), 3)})
                i += window   # non-overlapping
            i += 1
    return pd.DataFrame(rows)


def surge_meta(thresh: float = 0.5, window: int = 20) -> dict:
    """Meta-analysis of surges: base rate of continuation, sector mix, momentum."""
    ep = surge_episodes(thresh, window)
    if ep.empty:
        return {"n": 0}
    cont = (ep.fwd_20d > 0).mean()
    return {
        "n_episodes": int(len(ep)),
        "avg_fwd_20d": round(float(ep.fwd_20d.mean()), 4),
        "median_fwd_20d": round(float(ep.fwd_20d.median()), 4),
        "continued_up_rate": round(float(cont), 3),
        "avg_prior_momentum": round(float(ep.prior_mom.mean()), 4),
        "top_sectors": ep.sector.value_counts().head(6).to_dict(),
        "note": (f">= {thresh:.0%} in {window}d. Forward 20d after the surge averages "
                 f"{ep.fwd_20d.mean():+.1%} with a {cont:.0%} up-rate — i.e. surges "
                 f"{'tend to continue' if cont > 0.55 else 'mean-revert / are a coin flip'} "
                 f"(descriptive base rate, not a signal)."),
    }


def recent_surgers(months: int = 6, top: int = 20, min_adv: float = 5e6) -> pd.DataFrame:
    """Top liquid gainers over the trailing `months` (e.g. KPUS-type recent runs)."""
    df = data.load_prices()
    last = df.date.max()
    win = int(months * 21)
    df = df[df.adv_20 > min_adv]
    rows = []
    for sym, g in df.groupby("symbol", sort=False):
        g = g.sort_values("date")
        if g.date.iloc[-1] < last - pd.Timedelta(days=20) or len(g) < win:
            continue
        cum = g["cumlog"].to_numpy()
        r = float(np.exp(cum[-1] - cum[-win]) - 1)
        rows.append({"symbol": sym, "name": str(g["name"].iloc[-1]),
                     "sector": data.sector_name(g["sector"].iloc[-1]),
                     "ret": round(r, 3), "last_close": float(g["close"].iloc[-1])})
    d = pd.DataFrame(rows).sort_values("ret", ascending=False)
    return d.head(top).reset_index(drop=True)


def dip_rebounds(drop: float = -0.25, window: int = 20, fwd: int = 40,
                 min_adv: float = 5e6) -> dict:
    """Sharp-dip episodes (fell <= `drop` over `window` days) and their forward
    rebound — 'do crashes bounce back?'. Captures shock-driven dips like the
    Jun-2025 Israel-Iran war selloff and the recovery after."""
    df = data.load_prices()
    df = df[df.adv_20 > min_adv]
    rows = []
    for sym, g in df.groupby("symbol", sort=False):
        g = g.sort_values("date").reset_index(drop=True)
        cum = g["cumlog"].to_numpy(); n = len(g); i = window
        while i < n:
            past = np.exp(cum[i] - cum[i - window]) - 1
            if past <= drop:
                fw = np.exp(cum[min(i + fwd, n - 1)] - cum[i]) - 1
                rows.append({"symbol": sym, "sector": data.sector_name(g["sector"].iloc[i]),
                             "date": g["date"].iloc[i].date(), "dip": round(float(past), 3),
                             "fwd_rebound": round(float(fw), 3)})
                i += window
            i += 1
    ep = pd.DataFrame(rows)
    if ep.empty:
        return {"n": 0}
    return {"n_episodes": int(len(ep)),
            "avg_rebound": round(float(ep.fwd_rebound.mean()), 4),
            "median_rebound": round(float(ep.fwd_rebound.median()), 4),
            "rebound_positive_rate": round(float((ep.fwd_rebound > 0).mean()), 3),
            "top_dips": ep.sort_values("dip").head(12).to_dict(orient="records"),
            "note": (f"Fell <= {drop:.0%} in {window}d. Forward {fwd}d averages "
                     f"{ep.fwd_rebound.mean():+.1%}, positive {int((ep.fwd_rebound>0).mean()*100)}% "
                     f"of the time — sharp dips {'tend to bounce' if (ep.fwd_rebound>0).mean()>0.55 else 'do NOT reliably bounce'} "
                     f"(descriptive base rate).")}


def shock_response(min_adv: float = config.MIN_ADV) -> pd.DataFrame:
    """Index behaviour around each external-shock event: dip into it and rebound
    after (the war/oil-spike playbook)."""
    from analysis.events import load_events
    ev = load_events()
    if ev.empty:
        return pd.DataFrame()
    ev = ev[ev.type.isin(["external_shock", "political", "commodity"])]
    mkt = data.market_index(min_adv)
    loglvl = np.log1p(mkt).cumsum()
    days = mkt.index
    rows = []
    for e in ev.itertuples():
        pos = days.searchsorted(pd.Timestamp(e.date))
        if pos < 10 or pos + 40 >= len(days):
            continue
        pre = float(np.expm1(loglvl.iloc[pos] - loglvl.iloc[pos - 10]))     # 10d into event
        post = float(np.expm1(loglvl.iloc[min(pos + 20, len(days) - 1)] - loglvl.iloc[pos]))  # 20d after
        rows.append({"date": str(e.date.date()), "title": e.title[:46],
                     "into_event_10d": round(pre, 3), "rebound_20d": round(post, 3)})
    return pd.DataFrame(rows).sort_values("into_event_10d")


def sector_booms(top_q: float = 0.9) -> pd.DataFrame:
    """Sector-months in the top decile of sector monthly return, with the rate
    level & direction that month — 'what backdrop accompanies sector booms'."""
    from analysis.connections import sector_monthly_returns
    from pakterm.sectors import SECTOR_NAMES, is_operating_sector
    op_names = {v for k, v in SECTOR_NAMES.items() if is_operating_sector(k)}
    sm = sector_monthly_returns()
    sm = sm[[c for c in sm.columns if c in op_names]]   # operating sectors only
    rate = data.load_macro_monthly().get("policy_rate")
    rows = []
    thr = sm.stack().quantile(top_q)
    for period, row in sm.iterrows():
        for sec, val in row.items():
            # cap implausible thin-basket artifacts (>80%/month for an EW sector)
            if pd.notna(val) and val >= thr and val <= 0.8:
                rr = None
                if rate is not None:
                    rr = rate.get(period.to_timestamp("M"))
                rows.append({"month": str(period), "sector": sec,
                             "ret": round(float(val), 3),
                             "policy_rate": None if rr is None or pd.isna(rr) else round(float(rr), 2)})
    d = pd.DataFrame(rows).sort_values("ret", ascending=False)
    return d.head(40)


if __name__ == "__main__":
    print("=== MULTI-BAGGERS (peak multiple, liquid) ===")
    print(multibaggers(3.0).to_string(index=False))
    print("\n=== BANK / RATE-LEVEL THESIS ===")
    import json
    print(json.dumps(bank_rate_thesis(), indent=1, default=str))
    print("\n=== SURGE META (>=50% in 20d) ===")
    print(json.dumps(surge_meta(), indent=1, default=str))
