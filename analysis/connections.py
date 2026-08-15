"""Connection engine: empirical correlations between sectors and macro factors.

Honesty first. With ~85 monthly observations and dozens of sector x factor
pairs, many correlations are spurious. Every table therefore carries the sample
size and a t-stat; |t|<2 (~p>0.05) is flagged as not significant. These are
DESCRIPTIVE structural readings, not a fitted predictor. Where a curated prior
(sector graph) exists, we surface prior-vs-empirical side by side so the user
sees agreement/disagreement rather than trusting either blindly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pakterm import config, data


def sector_monthly_returns(min_adv: float = config.MIN_ADV) -> pd.DataFrame:
    sr = data.sector_daily_returns(min_adv)
    return data.to_monthly_returns(sr)


def sector_monthly_excess(min_adv: float = config.MIN_ADV) -> pd.DataFrame:
    """Sector monthly return MINUS the market monthly return.

    Strips the common market move (beta). This is the correct lens for the
    curated *cross-sectional* priors (e.g. 'exporters outperform when PKR falls'),
    which are claims about RELATIVE performance, not absolute direction. In a
    crisis every sector falls together, so raw correlations are dominated by the
    market and understate cross-sectional tilts.
    """
    sec = sector_monthly_returns(min_adv)
    mkt = data.to_monthly_returns(data.market_index(min_adv))
    return sec.sub(mkt, axis=0)


def macro_monthly_deltas() -> pd.DataFrame:
    """Month-over-month macro 'shocks' (the changes markets react to)."""
    m = data.load_macro_monthly()
    if m.empty:
        return pd.DataFrame()
    # align to PeriodIndex('M') so it joins with sector monthly returns
    m = m.copy()
    m.index = m.index.to_period("M")
    out = pd.DataFrame(index=m.index)
    if "policy_rate" in m:      out["d_policy_rate"] = m["policy_rate"].diff()
    if "cpi_yoy" in m:          out["d_cpi_yoy"] = m["cpi_yoy"].diff()
    if "pkr_usd" in m:          out["pkr_depr"] = m["pkr_usd"].pct_change()
    if "brent_usd" in m:        out["oil_ret"] = m["brent_usd"].pct_change()
    if "fx_reserves_sbp_bn" in m: out["reserves_chg"] = m["fx_reserves_sbp_bn"].pct_change()
    if "remittances_bn" in m:   out["remit_chg"] = m["remittances_bn"].pct_change()
    return out.dropna(how="all")


def _corr_t(x: pd.Series, y: pd.Series) -> tuple[float, int, float]:
    j = pd.concat([x, y], axis=1).dropna()
    n = len(j)
    if n < 8:
        return (np.nan, n, np.nan)
    r = j.iloc[:, 0].corr(j.iloc[:, 1])
    t = r * np.sqrt((n - 2) / max(1e-9, 1 - r * r))
    return (float(r), int(n), float(t))


def sector_macro_corr(lag: int = 0, min_adv: float = config.MIN_ADV,
                      relative: bool = False) -> pd.DataFrame:
    """Long tidy table: sector x macro-factor correlation with t-stat and sig flag.

    lag=0 contemporaneous; lag=1 tests macro shock this month -> sector next month.
    relative=True uses market-adjusted (sector-minus-market) returns, isolating
    cross-sectional tilts from the market-wide move.
    """
    sec = sector_monthly_excess(min_adv) if relative else sector_monthly_returns(min_adv)
    mac = macro_monthly_deltas()
    if mac.empty or sec.empty:
        return pd.DataFrame(columns=["sector", "factor", "corr", "n", "t", "sig", "lag"])
    rows = []
    for f in mac.columns:
        fx = mac[f]
        for s in sec.columns:
            sy = sec[s].shift(-lag) if lag else sec[s]
            r, n, t = _corr_t(fx, sy)
            if np.isnan(r):
                continue
            rows.append({"sector": s, "factor": f, "corr": round(r, 3), "n": n,
                         "t": round(t, 2), "sig": bool(abs(t) >= 2), "lag": lag,
                         "rel": relative})
    cols = ["sector", "factor", "corr", "n", "t", "sig", "lag", "rel"]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows).sort_values("t", key=lambda c: c.abs(), ascending=False)


def cross_sector_corr(min_adv: float = config.MIN_ADV) -> pd.DataFrame:
    """Sector x sector monthly-return correlation matrix (full-sample)."""
    sec = sector_monthly_returns(min_adv).dropna(axis=1, how="all")
    sec = sec.loc[:, sec.std(numeric_only=True) > 0]   # drop zero-variance cols
    with np.errstate(invalid="ignore", divide="ignore"):
        return sec.corr(min_periods=8).round(2)


def lead_lag(min_adv: float = config.MIN_ADV, top: int = 25) -> pd.DataFrame:
    """Does sector A (this month) predict sector B (next month)? corr(A_t, B_{t+1})."""
    sec = sector_monthly_returns(min_adv).dropna(axis=1, how="all")
    rows = []
    for a in sec.columns:
        for b in sec.columns:
            if a == b:
                continue
            r, n, t = _corr_t(sec[a], sec[b].shift(-1))
            if np.isnan(r):
                continue
            rows.append({"leader": a, "follower": b, "corr": round(r, 3),
                         "n": n, "t": round(t, 2)})
    df = pd.DataFrame(rows)
    return df.reindex(df.t.abs().sort_values(ascending=False).index).head(top)


def prior_vs_empirical(graph: dict, min_adv: float = config.MIN_ADV) -> pd.DataFrame:
    """Compare curated macro_sensitivity priors against measured correlations.

    graph: parsed knowledge/sector_graph.json. Maps its factor priors to the
    empirical macro-delta correlations so the user sees where data agrees with
    the story. Uses MARKET-ADJUSTED correlations because the priors are
    cross-sectional claims. Empty if graph/macro not available.
    """
    smc = sector_macro_corr(lag=0, min_adv=min_adv, relative=True)
    if smc.empty or not graph:
        return pd.DataFrame()
    factor_map = {"policy_rate": "d_policy_rate", "pkr_depreciation": "pkr_depr",
                  "oil": "oil_ret", "remittances": "remit_chg"}
    emp = {(r.sector, r.factor): (r.corr, r.t) for r in smc.itertuples()}
    rows = []
    for s in graph.get("sectors", []):
        name = s.get("name")
        ms = s.get("macro_sensitivity", {})
        for prior_key, fac in factor_map.items():
            if prior_key not in ms:
                continue
            e = emp.get((name, fac))
            if e is None:
                continue
            prior = ms[prior_key]
            agree = np.sign(prior) == np.sign(e[0]) if prior and e[0] else None
            rows.append({"sector": name, "factor": prior_key,
                         "prior": prior, "empirical_corr": round(e[0], 3),
                         "t": round(e[1], 2),
                         "agrees": None if agree is None else bool(agree)})
    df = pd.DataFrame(rows)
    if not df.empty:
        df["agrees"] = df["agrees"].astype("boolean")   # nullable bool, safe .mean()
    return df


def agreement_rate(pve: pd.DataFrame, min_abs_t: float = 0.0) -> dict:
    """Fraction of curated priors whose sign matches the market-adjusted data."""
    if pve.empty:
        return {"rate": None, "n": 0}
    d = pve[pve["t"].abs() >= min_abs_t].dropna(subset=["agrees"])
    n = len(d)
    return {"rate": round(float((d["agrees"] == True).sum() / n), 3) if n else None,  # noqa: E712
            "n": int(n), "min_abs_t": min_abs_t}


if __name__ == "__main__":
    print("=== cross-sector correlation (head) ===")
    cc = cross_sector_corr()
    print(cc.iloc[:6, :6].to_string())
    smc = sector_macro_corr()
    if not smc.empty:
        print("\n=== strongest sector x macro correlations ===")
        print(smc.head(15).to_string(index=False))
    else:
        print("\n(macro not seeded yet -> sector x macro table empty)")
