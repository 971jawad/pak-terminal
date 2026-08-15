"""Surge-propensity predictor — built from the meta-analysis, validated HONESTLY.

Question: from observable pre-surge metrics, can we rank stocks by their odds of
a big move (>= `SURGE` over the next `HORIZON` trading days)?

Method:
  * Features at each month-end use ONLY trailing data (no look-ahead): multi-horizon
    momentum, volatility, liquidity level + growth, distance from 52w/20d highs,
    price level, and market/sector context.
  * Label: did the stock's max close over the NEXT `HORIZON` days exceed today's by
    >= `SURGE`?
  * Walk-forward: train on months before `CUTOFF`, test strictly after. We report
    out-of-sample AUC and a decile-lift table (does the top predicted decile
    actually surge more often?). This is the ONLY honest way to know if the metrics
    carry signal. No in-sample curve-fitting, no "perfect backtest".

If the OOS lift is ~1x the base rate, the metrics don't predict surges and we say
so. If the top decile genuinely surges more, that lift — modest and measured — is
the real, usable output.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from pakterm import config, data

HORIZON = 60          # trading days (~3 months)
SURGE = 0.40          # +40% counts as a "surge"
CUTOFF = "2024-01-01"

FEATURES = ["ret_20", "ret_60", "ret_120", "vol_20", "dist_252h", "dist_20h",
            "adv_growth", "log_adv", "log_price", "mkt_ret_20", "rel_ret_60"]


@lru_cache(maxsize=2)
def build_panel(min_adv: float = config.MIN_ADV) -> pd.DataFrame:
    df = data.load_prices().copy()
    g = df.groupby("symbol", sort=False)
    cl = g["cumlog"]
    df["ret_20"] = np.expm1(df.cumlog - cl.shift(20))
    df["ret_60"] = np.expm1(df.cumlog - cl.shift(60))
    df["ret_120"] = np.expm1(df.cumlog - cl.shift(120))
    df["vol_20"] = g["r1"].transform(lambda s: s.rolling(20, min_periods=10).std())
    roll_max_252 = cl.transform(lambda s: s.rolling(252, min_periods=60).max())
    roll_max_20 = cl.transform(lambda s: s.rolling(20, min_periods=10).max())
    df["dist_252h"] = np.expm1(df.cumlog - roll_max_252)
    df["dist_20h"] = np.expm1(df.cumlog - roll_max_20)
    adv60 = g["value"].transform(lambda s: s.rolling(60, min_periods=20).median())
    df["adv_growth"] = np.log1p(df.adv_20) - np.log1p(adv60)
    df["log_adv"] = np.log1p(df.adv_20)
    df["log_price"] = np.log(df.close.clip(lower=0.1))

    # market + sector context
    liq = df[df.adv_20 > min_adv]
    mkt = liq.groupby("date")["r1"].mean()
    mcum = np.log1p(mkt).cumsum()
    df = df.merge(np.expm1(mcum - mcum.shift(20)).rename("mkt_ret_20"),
                  left_on="date", right_index=True, how="left")
    sec = df.groupby(["date", "sector"])["ret_60"].transform("median")
    df["rel_ret_60"] = df.ret_60 - sec

    # forward label: max level over next HORIZON days vs today (per-symbol)
    df["_lvl"] = np.exp(df.cumlog)
    df["fwd_max"] = df.groupby("symbol", sort=False)["_lvl"].transform(
        lambda s: s.rolling(HORIZON).max().shift(-HORIZON))
    df["surge"] = (df.fwd_max / df._lvl - 1 >= SURGE).astype(float)
    df.loc[df.fwd_max.isna(), "surge"] = np.nan

    # sample: liquid, tradable month-ends only (reduce overlap)
    df["ym"] = df.date.dt.to_period("M")
    df = df[df.adv_20 > min_adv]
    lastday = df.groupby(["symbol", "ym"])["date"].transform("max")
    panel = df[(df.date == lastday)].dropna(subset=FEATURES + ["surge"]).copy()
    return panel


def walkforward(min_adv: float = config.MIN_ADV) -> dict:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    p = build_panel(min_adv)
    tr = p[p.date < CUTOFF]
    te = p[p.date >= CUTOFF]
    if len(te) < 200 or tr.surge.sum() < 30:
        return {"error": "insufficient data", "n_train": len(tr), "n_test": len(te)}
    Xtr, ytr = tr[FEATURES].to_numpy(np.float32), tr.surge.to_numpy()
    Xte, yte = te[FEATURES].to_numpy(np.float32), te.surge.to_numpy()
    m = HistGradientBoostingClassifier(max_depth=4, max_iter=250, learning_rate=0.05,
                                       min_samples_leaf=120, l2_regularization=1.0,
                                       random_state=42)
    m.fit(Xtr, ytr)
    prob = m.predict_proba(Xte)[:, 1]
    auc = float(roc_auc_score(yte, prob))
    base = float(yte.mean())
    # decile lift on the test set
    te = te.assign(prob=prob)
    te["decile"] = pd.qcut(te.prob.rank(method="first"), 10, labels=False)
    dl = te.groupby("decile")["surge"].agg(["mean", "size"]).reset_index()
    dl["lift"] = (dl["mean"] / base).round(2)
    top = dl[dl.decile == 9].iloc[0]
    # permutation importance (cheap subsample)
    from sklearn.inspection import permutation_importance
    idx = np.random.RandomState(0).choice(len(Xte), min(1500, len(Xte)), replace=False)
    pi = permutation_importance(m, Xte[idx], yte[idx], n_repeats=4, random_state=0,
                                scoring="roc_auc")
    imp = sorted(zip(FEATURES, pi.importances_mean), key=lambda x: -x[1])

    # current screen: score latest month-end rows
    latest = build_panel(min_adv)  # cached deps; reuse full then filter latest
    lastm = latest.date.max()
    cur = latest[latest.date == lastm].copy()
    if len(cur):
        cur["prob"] = m.predict_proba(cur[FEATURES].to_numpy(np.float32))[:, 1]
        screen = (cur.sort_values("prob", ascending=False)
                  .head(15)[["symbol", "name", "sector_name", "prob", "ret_60", "dist_252h"]])
        screen = screen.assign(name=screen.name.astype(str)).round(3).to_dict(orient="records")
    else:
        screen = []

    verdict = (f"top-decile surge rate {top['mean']:.0%} vs {base:.0%} base "
               f"= {top['lift']:.1f}x lift, OOS AUC {auc:.2f}. "
               + ("A real, modest edge: the metrics rank surge odds better than chance."
                  if auc > 0.56 and top["lift"] > 1.3 else
                  "Essentially no out-of-sample edge — the metrics do not predict surges "
                  "(as expected; big moves are largely unforecastable from price alone)."))
    return {"base_rate": round(base, 3), "oos_auc": round(auc, 3),
            "surge_def": f">= {SURGE:.0%} in {HORIZON}d", "cutoff": CUTOFF,
            "n_train": len(tr), "n_test": len(te),
            "decile_lift": dl.round(3).to_dict(orient="records"),
            "top_features": [{"feature": f, "auc_drop": round(float(v), 4)} for f, v in imp[:8]],
            "screen": screen, "verdict": verdict}


def sector_surge_base_rates(min_adv: float = config.MIN_ADV) -> pd.DataFrame:
    """Which sectors' stocks surge most often historically (base-rate table)."""
    p = build_panel(min_adv)
    g = p.groupby("sector_name")["surge"]
    out = pd.DataFrame({"surge_rate": g.mean().round(3), "n": g.size()})
    return out[out.n >= 50].sort_values("surge_rate", ascending=False)


if __name__ == "__main__":
    import json
    r = walkforward()
    print("=== SURGE PREDICTOR (out-of-sample walk-forward) ===")
    print(json.dumps({k: v for k, v in r.items() if k not in ("decile_lift", "screen")}, indent=1, default=str))
    print("\ndecile lift (test):")
    for d in r.get("decile_lift", []):
        print(f"  decile {int(d['decile'])}: surge {d['mean']:.0%} (n={int(d['size'])}) lift {d['lift']}x")
    print("\ncurrent top surge-propensity screen:")
    for s in r.get("screen", [])[:10]:
        print(f"  {s['symbol']:>7} {s['sector_name'][:22]:22} p={s['prob']:.2f} ret60={s['ret_60']:+.0%}")
    print("\n=== SECTOR SURGE BASE RATES ===")
    print(sector_surge_base_rates().to_string())
