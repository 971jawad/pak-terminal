"""Market regime: the ONE verified edge (trend-following) + an honest macro overlay.

The trend-ensemble signal is the real, out-of-sample, cost-surviving edge carried
over verbatim from psx-quant (Sharpe ~1.15 -> ~1.45, max DD ~-42% -> ~-25%). The
macro overlay is a SMALL set of economically-grounded context factors (policy-rate
direction, PKR trend, reserves trend). It is deliberately NOT a fitted predictor —
with ~85 monthly points that would overfit. It only tilts/annotates the primary
trend signal. See reports for the honesty statement.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pakterm import config, data


# ---------------------------------------------------------------- trend edge

def ma_signal(mkt: pd.Series, n: int) -> pd.Series:
    lvl = (1 + mkt).cumprod()
    return (lvl > lvl.rolling(n).mean()).astype(float)


def mom_signal(mkt: pd.Series, n: int) -> pd.Series:
    return (mkt.rolling(n).sum() > 0).astype(float)


def ensemble_signal(mkt: pd.Series, ns=(20, 50, 100, 200)) -> pd.Series:
    return pd.concat([ma_signal(mkt, n) for n in ns], axis=1).mean(axis=1)


def timed_returns(mkt: pd.Series, signal: pd.Series, cost: float = 0.003,
                  cash_annual: float = config.CASH_ANNUAL) -> pd.Series:
    pos = signal.shift(1).fillna(0.0).clip(0, 1)
    cash_daily = (1 + cash_annual) ** (1 / config.PPY) - 1
    switch = pos.diff().abs().fillna(0.0)
    return pos * mkt + (1 - pos) * cash_daily - switch * cost


def _perf(ret: pd.Series) -> dict:
    r = ret.dropna()
    eq = (1 + r).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    cagr = eq.iloc[-1] ** (config.PPY / len(r)) - 1
    sharpe = r.mean() / (r.std() + 1e-12) * np.sqrt(config.PPY)
    return {"cagr": float(cagr), "sharpe": float(sharpe), "max_dd": float(dd)}


def timing_regime(min_adv: float = config.MIN_ADV) -> dict:
    """Today's RISK-ON/OFF signal = trend-ensemble exposure (0..1) + filter states."""
    mkt = data.market_index(min_adv)
    lvl = (1 + mkt).cumprod()
    states = {}
    for n in (20, 50, 100, 200):
        ma = lvl.rolling(n).mean().iloc[-1]
        states[f"above_MA{n}"] = bool(lvl.iloc[-1] > ma)
    exposure = sum(states.values()) / len(states)
    return {
        "as_of": str(mkt.index[-1].date()),
        "exposure": round(exposure, 2),
        "signal": "RISK-ON" if exposure >= 0.5 else "RISK-OFF",
        "filters": states,
        "index_level": round(float(lvl.iloc[-1]), 4),
        "index_ret_20d": round(float(mkt.tail(20).sum()), 4),
        "index_ret_60d": round(float(mkt.tail(60).sum()), 4),
    }


def verify_edge(min_adv: float = config.MIN_ADV) -> pd.DataFrame:
    """Reproduce the verified timing table live (buy&hold vs trend variants)."""
    mkt = data.market_index(min_adv)
    rows = {"buy&hold": mkt}
    for n in (50, 100, 200):
        rows[f"trend_MA{n}"] = timed_returns(mkt, ma_signal(mkt, n))
    rows["trend_ensemble"] = timed_returns(mkt, ensemble_signal(mkt))
    out = []
    for name, r in rows.items():
        p = _perf(r)
        out.append({"strategy": name, "CAGR": p["cagr"], "Sharpe": p["sharpe"],
                    "maxDD": p["max_dd"]})
    return pd.DataFrame(out).set_index("strategy").round(3)


# ---------------------------------------------------------------- macro overlay

def macro_overlay() -> dict:
    """A few robust, economically-signed macro context factors -> tilt in [-1,1].

    NOT a fitted model. Each factor has a strong prior and is directionally
    obvious; the score is a transparent average, shown as CONTEXT next to the
    (primary) trend signal. Degrades gracefully if macro is unseeded.
    """
    m = data.load_macro_monthly()
    factors: dict[str, dict] = {}

    def add(name, value, prior):
        factors[name] = {"value": value, "signal": prior}

    if not m.empty:
        # policy-rate direction: cutting = tailwind for equities (lower discount
        # rate, cheaper leverage); hiking = headwind. 6-month change.
        if "policy_rate" in m and m["policy_rate"].notna().sum() >= 7:
            pr = m["policy_rate"].dropna()
            d6 = pr.iloc[-1] - pr.iloc[-7] if len(pr) >= 7 else 0.0
            add("policy_rate_6m_change_pp", round(float(d6), 2),
                +1 if d6 < -0.25 else (-1 if d6 > 0.25 else 0))
        # PKR trend: rapid depreciation = macro stress (risk-off for the broad
        # market, though a tailwind for exporters — handled in the sector graph).
        if "pkr_usd" in m and m["pkr_usd"].notna().sum() >= 4:
            fx = m["pkr_usd"].dropna()
            dep3 = fx.iloc[-1] / fx.iloc[-4] - 1 if len(fx) >= 4 else 0.0
            add("pkr_depreciation_3m", round(float(dep3), 3),
                -1 if dep3 > 0.05 else (+1 if dep3 < -0.02 else 0))
        # reserves trend: rising = improving external position = risk-on.
        if "fx_reserves_sbp_bn" in m and m["fx_reserves_sbp_bn"].notna().sum() >= 4:
            rv = m["fx_reserves_sbp_bn"].dropna()
            ch3 = rv.iloc[-1] / rv.iloc[-4] - 1 if len(rv) >= 4 else 0.0
            add("reserves_3m_change", round(float(ch3), 3),
                +1 if ch3 > 0.05 else (-1 if ch3 < -0.05 else 0))
        # inflation direction: falling CPI = room to cut = tailwind.
        if "cpi_yoy" in m and m["cpi_yoy"].notna().sum() >= 4:
            cpi = m["cpi_yoy"].dropna()
            dc3 = cpi.iloc[-1] - cpi.iloc[-4] if len(cpi) >= 4 else 0.0
            add("cpi_yoy_3m_change_pp", round(float(dc3), 2),
                +1 if dc3 < -1 else (-1 if dc3 > 1 else 0))

    signals = [f["signal"] for f in factors.values()]
    score = round(sum(signals) / len(signals), 2) if signals else None
    tilt = ("supportive" if score is not None and score > 0.25 else
            "restrictive" if score is not None and score < -0.25 else
            "neutral" if score is not None else "unseeded")
    return {"factors": factors, "score": score, "tilt": tilt,
            "note": "context overlay only; primary signal is the verified trend edge"}


def combined_view(min_adv: float = config.MIN_ADV) -> dict:
    return {"timing": timing_regime(min_adv), "macro": macro_overlay()}


if __name__ == "__main__":
    print("=== VERIFIED TREND EDGE (live reproduction) ===")
    print(verify_edge().to_string())
    v = combined_view()
    print("\n=== TIMING REGIME (primary signal) ===")
    print(v["timing"])
    print("\n=== MACRO OVERLAY (context only) ===")
    print(v["macro"])
