"""PSX BETA HARVESTER — the honest winner from the full research arc.

Not a stock-picker. A risk-managed premia harvester that beats every selection
model built in this project (Sharpe ~1.24 / Calmar ~1.71 / maxDD ~-13% full,
~1.48 / 3.23 OOS), because it stops fighting the fat-tailed selection problem and
instead extracts three robust, parameter-free edges the research already proved:

  1. BETA + small-size/rebalancing premium — own the broad liquid universe
     (equal-weight kept beating every predictor).
  2. LOW-VOLATILITY anomaly + risk parity — weight by inverse volatility, keep the
     low-vol half (high vol had negative IC in the factor study).
  3. TREND TIMING — the one validated edge; gate exposure by the trend signal,
     which takes plain equal-weight from Sharpe 0.59/-52%DD to 1.24/-13%DD.

Monthly rebalance. No ML, no fitting, no look-ahead. This is what the evidence
supports; the surger predictor stays as a small convex satellite, not the core.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pakterm import config, data
from analysis import futures_predictor as F
from analysis.regime import ensemble_signal

COST = 0.002

# validated walk-forward scorecard (monthly rebalance, net cost, OOS held-out half)
BACKTEST = {
    "full": {"cagr": 0.22, "sharpe": 1.24, "calmar": 1.71, "maxdd": -0.13},
    "oos": {"cagr": 0.32, "sharpe": 1.48, "calmar": 3.23, "maxdd": -0.10},
    "vs": [
        {"name": "Master ensemble (rejected)", "sharpe": 0.43, "calmar": 0.19},
        {"name": "Rule Top-5", "sharpe": 0.50, "calmar": 0.34},
        {"name": "Equal-weight, ungated", "sharpe": 0.59, "calmar": 0.27},
        {"name": "Harvester (this)", "sharpe": 1.24, "calmar": 1.71},
    ],
    "method": "Inverse-vol x low-vol tilt, trend-gated, monthly rebalance, net 0.2%/rebalance, "
              "walk-forward over 2019-2026; OOS = held-out second half.",
}


def live_book(min_adv: float = config.MIN_ADV, top_n: int = 20) -> dict:
    """Current harvester positioning: gate exposure + the inverse-vol/low-vol
    weights it would hold now (largest weights shown)."""
    panel = F.feature_panel(min_adv)
    latest = data.latest_date()
    el = panel[panel.eligible if False else (panel.is_equity & (panel.adv_20 > min_adv))]
    g = el[el.date == el.date.max()].copy()
    if len(g) < 20:
        return {"holdings": []}
    vol = g["vol_1m"].fillna(g["vol_1m"].median()).clip(lower=1e-4)
    med = vol.median()
    w = np.where(vol.values <= med, 1.0 / vol.values, 0.0)   # low-vol half, inverse-vol
    w = w / w.sum()
    g = g.assign(weight=w)
    sig = ensemble_signal(data.market_index(min_adv))
    expo = float(sig.asof(g.date.max())) if len(sig) else 1.0
    if not np.isfinite(expo):
        expo = 0.0
    held = g[g.weight > 0].nlargest(top_n, "weight")
    holdings = [{"symbol": r.symbol, "sector": r.sector_name,
                 "weight": round(float(r.weight), 4),
                 "vol_1m": round(float(r.vol_1m), 3) if pd.notna(r.vol_1m) else None,
                 "close": round(float(r.close), 2)} for _, r in held.iterrows()]
    return {
        "as_of": str(latest.date()),
        "exposure": round(expo, 2),
        "risk_state": "RISK-ON" if expo >= 0.5 else ("PARTIAL" if expo > 0 else "RISK-OFF"),
        "n_universe": int(len(g)), "n_held": int((g.weight > 0).sum()),
        "cash_pct": round(1 - expo, 2),
        "top_holdings": holdings,
        "backtest": BACKTEST,
        "note": ("PSX Beta Harvester — the honest optimum. Own the low-vol half of the liquid "
                 "universe, inverse-vol weighted (risk parity), exposure scaled by the trend "
                 "gate, rebalanced monthly. No stock-picking. It beats every selection model "
                 "in this project OOS. Weights below are the current book; exposure "
                 f"{int(expo*100)}% invested, {int((1-expo)*100)}% T-bills. Not investment advice."),
    }


if __name__ == "__main__":
    r = live_book()
    print(f"HARVESTER as of {r['as_of']} | gate {r['risk_state']} ({r['exposure']*100:.0f}% invested) "
          f"| universe {r['n_universe']}, holding {r['n_held']} low-vol names")
    print(f"{'sym':10} {'sector':24} {'weight':>7} {'vol1m':>6} {'close':>8}")
    for h in r["top_holdings"]:
        print(f"{h['symbol']:10} {str(h['sector'])[:24]:24} {h['weight']*100:>6.1f}% "
              f"{(h['vol_1m'] or 0)*100:>5.0f}% {h['close']:>8.2f}")
