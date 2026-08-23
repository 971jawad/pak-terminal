"""HYB — a hybrid futures strategy that fuses the whole research arc into one
risk-optimised book, tested walk-forward / OOS with no look-ahead.

Design (each piece earned its place empirically earlier):
  * RANK (offense): the transparent rule that beat ML — z(3m momentum) +
    z(closeness to 52w high) + z(liquidity growth); optional quality tilt that
    subtracts z(vol)+z(1-day-spike) to shed the worst crashers.
  * WEIGHT (Sharpe/drawdown): inverse-volatility across the top-K, so the
    crash-prone names are sized down while the moonshots stay in.
  * EXPOSURE (drawdown): CONTINUOUS timing gate — scale book exposure by the
    trend-signal strength (0..1) and sit the rest in T-bills, instead of binary.
  * OBJECTIVE: maximise Sharpe & Calmar (return / max-DD), because under leverage
    drawdown hurts super-linearly; leverage then scales at constant Sharpe.

Reported per horizon: precision@K (catch), CAGR, ann vol, Sharpe, max-DD, Calmar,
%positive — vs the plain gated equal-weight baseline. No look-ahead; non-overlapping.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pakterm import config, data
from analysis import futures_predictor as F
from analysis.regime import ensemble_signal

COST = 0.005


def _z(s):
    s = pd.Series(s, dtype=float)
    return (s - s.mean()) / (s.std() + 1e-9)


def backtest(H, K=5, weight="invvol", exposure="continuous", quality=0.0,
             min_adv=F.MIN_ADV, _lo=None, _hi=None):
    panel = F.feature_panel(min_adv)
    p = panel[panel.eligible].copy()
    if _lo is not None:
        p = p[p.ym >= _lo]
    if _hi is not None:
        p = p[p.ym < _hi]
    mac = data.load_macro_monthly(); mac.index = mac.index.to_period("M")
    sig = ensemble_signal(data.market_index(min_adv))
    months = sorted(p.ym.unique())
    ents = [m for m in months if p[p.ym == m][f"fwd_{H}"].notna().any()][::H]
    per_year = 12 / H
    rets, prec, rec, eqs, eq = [], [], [], [], 1.0
    for m in ents:
        g = p[p.ym == m].dropna(subset=[f"fwd_{H}"]).copy()
        if len(g) < 15:
            continue
        actual = set(g.nlargest(5, f"fwd_{H}").symbol)
        score = _z(g["mom_3m"]).values + _z(-g["dist_252h"]).values + _z(g["adv_growth"].fillna(0)).values
        if quality:
            score = score - quality * (_z(g["vol_1m"].fillna(g.vol_1m.median())).values
                                       + _z(g["maxup_1m"].fillna(0)).values)
        g = g.assign(score=score)
        top = g.nlargest(K, "score")
        ov = len(set(top.symbol) & actual)
        prec.append(ov / len(top))      # precision: fraction of OUR picks that were real top-5
        rec.append(ov / 5)              # recall: fraction of the real top-5 we caught
        # weights
        if weight == "invvol":
            iv = 1.0 / (top["vol_1m"].fillna(top.vol_1m.median()) + 1e-6)
            w = (iv / iv.sum()).values
        else:
            w = np.full(len(top), 1.0 / len(top))
        basket = float(np.sum(w * top[f"fwd_{H}"].values))
        # exposure (NaN before the 200d MA warms up -> stay in cash)
        e = float(sig.asof(g.date.max())) if len(sig) else 1.0
        if not np.isfinite(e):
            e = 0.0
        if exposure == "binary":
            e = 1.0 if e >= 0.5 else 0.0
        rate = float(mac["policy_rate"].reindex([m]).iloc[0]) if m in mac.index else 11.0
        carry = rate / 100 * H / 12
        # futures financing (carry) is charged on the invested portion; the
        # un-invested portion earns the T-bill rate. Consistent with strategy.py.
        net = e * (basket - COST - carry) + (1 - e) * carry
        rets.append(net); eq *= (1 + net); eqs.append(eq)
    rets, eqs = np.array(rets), np.array(eqs)
    if len(rets) < 4:
        return {}
    dd = float((eqs / np.maximum.accumulate(eqs) - 1).min())
    cagr = float(eqs[-1] ** (per_year / len(rets)) - 1)
    vol = float(rets.std(ddof=1) * np.sqrt(per_year))
    sharpe = float(rets.mean() * per_year / (vol + 1e-9))
    calmar = float(cagr / (abs(dd) + 1e-9))
    return {"H": H, "K": K, "weight": weight, "exposure": exposure, "quality": quality,
            "n": len(rets), "precision": round(float(np.mean(prec)), 3),
            "recall": round(float(np.mean(rec)), 3),
            "cagr": round(cagr, 3), "vol": round(vol, 3), "sharpe": round(sharpe, 2),
            "maxdd": round(dd, 3), "calmar": round(calmar, 2),
            "pct_pos": round(float((rets > 0).mean()), 3), "mult": round(float(eqs[-1]), 2)}


def backtest_window(H, lo=None, hi=None, **cfg):
    """Same backtest restricted to a date window — for held-out validation."""
    return backtest(H, _lo=lo, _hi=hi, **cfg)


def validate(H, configs, min_adv=F.MIN_ADV):
    """Split the sample in half: does a config's edge over baseline PERSIST in the
    unseen second half, or was it a sweep artifact (multiple-testing)?"""
    panel = F.feature_panel(min_adv)
    months = sorted(panel[panel.eligible].ym.unique())
    mid = months[len(months) // 2]
    rows = []
    for name, cfg in configs:
        a = backtest(H, min_adv=min_adv, _hi=mid, **cfg)
        b = backtest(H, min_adv=min_adv, _lo=mid, **cfg)
        if a and b:
            rows.append({"name": name,
                         "train_sharpe": a["sharpe"], "train_calmar": a["calmar"], "train_dd": a["maxdd"],
                         "test_sharpe": b["sharpe"], "test_calmar": b["calmar"], "test_dd": b["maxdd"],
                         "train_n": a["n"], "test_n": b["n"]})
    return pd.DataFrame(rows), str(mid)


def sweep(H=1, min_adv=F.MIN_ADV):
    configs = [
        ("baseline: EW, binary gate, K5", dict(K=5, weight="ew", exposure="binary", quality=0.0)),
        ("+ inverse-vol weight", dict(K=5, weight="invvol", exposure="binary", quality=0.0)),
        ("+ continuous exposure", dict(K=5, weight="invvol", exposure="continuous", quality=0.0)),
        ("+ wider basket K8", dict(K=8, weight="invvol", exposure="continuous", quality=0.0)),
        ("+ wider basket K10", dict(K=10, weight="invvol", exposure="continuous", quality=0.0)),
        ("+ quality tilt 0.5 (K8)", dict(K=8, weight="invvol", exposure="continuous", quality=0.5)),
        ("+ quality tilt 1.0 (K8)", dict(K=8, weight="invvol", exposure="continuous", quality=1.0)),
    ]
    rows = []
    for name, cfg in configs:
        r = backtest(H, min_adv=min_adv, **cfg)
        if r:
            r["name"] = name; rows.append(r)
    return rows


if __name__ == "__main__":
    for H in (1, 2, 3):
        print(f"\n===== HYB config sweep — {H}-month (walk-forward OOS) =====")
        print(f"{'config':>34} {'prec':>5} {'rec':>5} {'CAGR':>7} {'vol':>6} {'Shrp':>5} {'maxDD':>7} {'Calmar':>7} {'%pos':>5}")
        for r in sweep(H):
            print(f"{r['name']:>34} {r['precision']*100:>4.0f}% {r['recall']*100:>4.0f}% {r['cagr']*100:>+6.0f}% {r['vol']*100:>5.0f}% "
                  f"{r['sharpe']:>5.2f} {r['maxdd']*100:>+6.0f}% {r['calmar']:>7.2f} {r['pct_pos']*100:>4.0f}%")
