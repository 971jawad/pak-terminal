"""CORRECTOR — a LIVE conviction overlay on the mechanical surger picks.

HONEST SCOPE (read before trusting it):
  * TECHNICAL read + VALUATION: computed from our own data -> reliable, and in
    principle backtestable (though technicals are just more price features we
    already tested; they don't add proven edge).
  * NEWS / CATALYST: a LIVE decision aid only. It CANNOT be honestly backtested
    over history, because there is no point-in-time news archive — searching
    today for "what drove X in July-2023" returns hindsight-written articles,
    which is lookahead contamination. So the corrector re-ranks/annotates the
    CURRENT month's picks for YOUR judgment; it is not a proven precision or
    drawdown improver. Where a real pre-month catalyst exists (e.g. the refinery
    policy approved end-July-2026 -> Aug refinery surge) it is genuinely useful;
    where the surger is just noise, it can invent nothing.
"""
from __future__ import annotations
import numpy as np, pandas as pd
from pakterm import data


def technical_read(symbol: str, as_of=None) -> dict:
    """TradingView-style technical summary computed from price history to `as_of`
    (default: latest). Uses only data up to as_of -> no lookahead."""
    df = data.load_prices()
    g = df[df.symbol == symbol].sort_values("date")
    if as_of is not None:
        g = g[g.date <= pd.Timestamp(as_of)]
    if len(g) < 60:
        return {"symbol": symbol, "rating": "n/a"}
    close = g["close"].to_numpy(); r1 = g["r1"].to_numpy()
    c = close[-1]
    ma = lambda n: close[-n:].mean() if len(close) >= n else np.nan
    ma20, ma50, ma200 = ma(20), ma(50), ma(200)
    # RSI(14)
    d = np.diff(close[-15:]); up = d[d > 0].sum(); dn = -d[d < 0].sum()
    rsi = 100 - 100 / (1 + (up / dn)) if dn > 0 else 100.0
    hi252 = close[-252:].max() if len(close) >= 252 else close.max()
    dist_hi = c / hi252 - 1
    adv20 = (g["close"] * g["volume"]).tail(20).median()
    adv60 = (g["close"] * g["volume"]).tail(60).median()
    vol_surge = adv20 / adv60 if adv60 > 0 else 1.0
    # scoring (each -1..+1)
    sig = {}
    sig["trend_MA"] = np.tanh(((c > ma20) + (ma20 > ma50) + (ma50 > ma200) - 1.5) / 1.5)
    sig["above_50MA"] = np.tanh((c / ma50 - 1) * 8) if ma50 else 0
    sig["rsi"] = -np.tanh((rsi - 55) / 20)                 # >75 overbought (negative), <45 room (positive)
    sig["near_52w_high"] = np.tanh((dist_hi + 0.08) * 10)  # near high = strong, but capped
    sig["volume"] = np.tanh((vol_surge - 1) * 3)
    score = float(np.mean(list(sig.values())))
    rating = ("Strong buy" if score > 0.4 else "Buy" if score > 0.12 else
              "Neutral" if score > -0.12 else "Sell" if score > -0.4 else "Strong sell")
    return {"symbol": symbol, "as_of": str(g.date.iloc[-1].date()), "close": round(float(c), 2),
            "rsi14": round(float(rsi), 0), "dist_52w_high": round(float(dist_hi), 3),
            "vol_surge": round(float(vol_surge), 2),
            "above": {"20d": bool(c > ma20), "50d": bool(c > ma50), "200d": bool(c > ma200)},
            "tech_score": round(score, 2), "rating": rating}


def valuation(symbol: str) -> dict:
    """Latest P/E, EPS, ROE from the fundamentals snapshot (if present)."""
    import json
    from pakterm import config
    f = config.DATA / "fundamentals.json"
    if not f.exists():
        return {}
    for c in json.loads(f.read_text(encoding="utf-8")).get("companies", []):
        if c.get("ticker") == symbol:
            return {k: c.get(k) for k in ("pe", "eps_ttm", "roe_pct", "earnings_growth_yoy_pct", "mkt_cap_pkr_bn")}
    return {}


def read_picks(symbols, as_of=None) -> list[dict]:
    out = []
    for s in symbols:
        t = technical_read(s, as_of)
        v = valuation(s)
        out.append({**t, "pe": v.get("pe"), "eps_growth": v.get("earnings_growth_yoy_pct")})
    return out
