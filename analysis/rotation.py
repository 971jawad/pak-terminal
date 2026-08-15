"""Sector-rotation predictor — the lever the surge autopsy uncovered.

~75% of top-5 surgers ride a booming SECTOR, and ~45% of a surge's magnitude is
just the sector rising. There are ~25 operating sectors (vs ~700 stocks), sector
baskets are far less noisy, and sector momentum is more persistent — so *sectors*
are the tractable unit. This module asks, honestly (walk-forward, purge, OOS):

  can we rank sectors each month and hold the top few for a 1/2/3-month horizon
  (aligned to the 30/60/90-day DFC), beating an equal-weight-all-sectors book —
  AND beating the futures carry hurdle (~policy_rate/12 per month)?

Cross-sectional macro features (rate/oil/PKR) DO help here, because different
sectors react differently to the same macro shock (banks vs cement vs exporters)
— the model learns those interactions, unlike single-stock ranking.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pakterm import config, data
from pakterm.sectors import SECTOR_NAMES, is_operating_sector

HORIZONS = (1, 2, 3)
TOPK = 3
MIN_TRAIN = 24
COST_RT = 0.004

FEATURES = ["mom_1", "mom_3", "mom_6", "mom_12", "rev_1", "vol_3", "rel_str_3",
            "rate_level", "rate_chg_3", "cpi_yoy", "pkr_chg_3", "oil_chg_3", "sector_code"]


def _panel(min_adv: float = config.MIN_ADV) -> pd.DataFrame:
    smr = data.to_monthly_returns(data.sector_daily_returns(min_adv))
    op = {v for k, v in SECTOR_NAMES.items() if is_operating_sector(k)}
    smr = smr[[c for c in smr.columns if c in op]].dropna(how="all")
    cum = (1 + smr).cumprod()
    mkt = data.to_monthly_returns(data.market_index(min_adv))
    mkt_cum = (1 + mkt).cumprod()
    codes = {s: i for i, s in enumerate(sorted(smr.columns))}

    mac = data.load_macro_monthly()
    mac.index = mac.index.to_period("M")

    rows = []
    for sec in smr.columns:
        c = cum[sec]
        f = pd.DataFrame(index=smr.index)
        f["mom_1"] = c / c.shift(1) - 1
        f["mom_3"] = c / c.shift(3) - 1
        f["mom_6"] = c / c.shift(6) - 1
        f["mom_12"] = c / c.shift(12) - 1
        f["rev_1"] = smr[sec]
        f["vol_3"] = smr[sec].rolling(3, min_periods=2).std()
        f["rel_str_3"] = (c / c.shift(3) - 1) - (mkt_cum / mkt_cum.shift(3) - 1)
        f["rate_level"] = mac["policy_rate"].reindex(f.index)
        f["rate_chg_3"] = mac["policy_rate"].reindex(f.index).diff(3)
        f["cpi_yoy"] = mac["cpi_yoy"].reindex(f.index)
        f["pkr_chg_3"] = mac["pkr_usd"].reindex(f.index).pct_change(3)
        f["oil_chg_3"] = mac["brent_usd"].reindex(f.index).pct_change(3)
        f["sector_code"] = codes[sec]
        for H in HORIZONS:
            f[f"fwd_{H}"] = c.shift(-H) / c - 1
        f["sector"] = sec
        f["ym"] = f.index
        rows.append(f)
    return pd.concat(rows, ignore_index=True)


def _reg():
    from sklearn.ensemble import HistGradientBoostingRegressor
    return HistGradientBoostingRegressor(max_depth=3, max_iter=250, learning_rate=0.05,
                                         min_samples_leaf=30, l2_regularization=1.0,
                                         random_state=42)


def walk_forward(H: int, min_adv: float = config.MIN_ADV) -> dict:
    p = _panel(min_adv).dropna(subset=FEATURES)
    months = sorted(p.ym.unique())
    recs, eq_top, eq_uni = [], [], []
    nxt = None
    mac = data.load_macro_monthly(); mac.index = mac.index.to_period("M")
    for i, t in enumerate(months):
        if i < MIN_TRAIN:
            continue
        tr = p[p.ym <= (t - H)].dropna(subset=[f"fwd_{H}"])
        te = p[p.ym == t]
        if len(tr) < 120 or len(te) < 8:
            continue
        m = _reg(); m.fit(tr[FEATURES].to_numpy(np.float32), tr[f"fwd_{H}"].to_numpy())
        te = te.assign(score=m.predict(te[FEATURES].to_numpy(np.float32)))
        ev = te.dropna(subset=[f"fwd_{H}"])
        if len(ev) < 8:
            continue
        top = te.nlargest(TOPK, "score")
        uni = float(ev[f"fwd_{H}"].mean())
        topret = float(top[f"fwd_{H}"].mean())
        ic = float(ev["score"].corr(ev[f"fwd_{H}"], method="spearman"))
        realized_top = set(ev.nlargest(TOPK, f"fwd_{H}").sector)
        prec = len(set(top.sector) & realized_top) / TOPK
        carry = float(mac["policy_rate"].reindex([t]).iloc[0] or 0) / 100 / 12 * H  # financing over H months
        recs.append({"ym": str(t), "top": topret, "uni": uni, "spread": topret - uni,
                     "ic": ic, "prec": prec, "carry": carry,
                     "net_top": topret - COST_RT - carry, "picks": list(top.sector)})
        if nxt is None or t >= nxt:
            eq_top.append(topret - COST_RT - carry); eq_uni.append(uni - carry); nxt = t + H
    if not recs:
        return {"H": H, "error": "insufficient"}
    r = pd.DataFrame(recs)
    ic_t = r.ic.mean() / (r.ic.std() + 1e-9) * np.sqrt(len(r))
    sp_t = r.spread.mean() / (r.spread.std() + 1e-9) * np.sqrt(len(r))
    per_year = 12 / H

    def _sh(a):
        a = np.array(a)
        return round(float(a.mean() * per_year / (a.std(ddof=1) * np.sqrt(per_year) + 1e-9)), 2) if len(a) > 2 else None

    def _cagr(a):
        a = np.array(a)
        return round(float(np.cumprod(1 + a)[-1] ** (per_year / len(a)) - 1), 3) if len(a) else None
    reliable = ic_t >= 2 and sp_t >= 1.5 and r.spread.mean() > 0.005
    return {
        "H": H, "n_months": int(len(r)), "topk": TOPK,
        "ic_mean": round(float(r.ic.mean()), 3), "ic_t": round(float(ic_t), 2),
        "top_avg_fwd": round(float(r.top.mean()), 4), "uni_avg_fwd": round(float(r.uni.mean()), 4),
        "spread": round(float(r.spread.mean()), 4), "spread_t": round(float(sp_t), 2),
        "hit_rate": round(float((r.spread > 0).mean()), 3),
        "precision_at_k": round(float(r.prec.mean()), 3),
        "avg_carry_per_period": round(float(r.carry.mean()), 4),
        "top_cagr_net_of_carry": _cagr(eq_top), "uni_cagr_net_of_carry": _cagr(eq_uni),
        "top_sharpe_net": _sh(eq_top), "uni_sharpe_net": _sh(eq_uni),
        "reliable": bool(reliable),
        "verdict": (f"USABLE: sectors rank OOS (IC t={ic_t:.1f}), top-{TOPK} beat all-sectors "
                    f"by {r.spread.mean():+.1%}/period (t={sp_t:.1f}), {(r.spread>0).mean():.0%} hit."
                    if reliable else
                    f"weak/none: IC t={ic_t:.1f}, spread {r.spread.mean():+.1%} (t={sp_t:.1f}), "
                    f"{(r.spread>0).mean():.0%} hit — sector rotation not reliably predictable here."),
    }


def current_top(min_adv: float = config.MIN_ADV) -> dict:
    p = _panel(min_adv).dropna(subset=FEATURES)
    last = max(p.ym.unique())
    out = {}
    for H in HORIZONS:
        tr = p[p.ym <= (last - H)].dropna(subset=[f"fwd_{H}"])
        cur = p[p.ym == last]
        if len(tr) < 120 or len(cur) < TOPK:
            out[H] = []
            continue
        m = _reg(); m.fit(tr[FEATURES].to_numpy(np.float32), tr[f"fwd_{H}"].to_numpy())
        cur = cur.assign(score=m.predict(cur[FEATURES].to_numpy(np.float32)))
        out[H] = [{"sector": r.sector, "score": round(float(r.score), 4),
                   "mom_3": round(float(r.mom_3), 3)}
                  for _, r in cur.nlargest(TOPK, "score").iterrows()]
    return {"as_of_month": str(last), "picks": out}


if __name__ == "__main__":
    import json
    for H in HORIZONS:
        r = walk_forward(H)
        print(f"\n=== SECTOR ROTATION {H}m (n={r.get('n_months')}) ===")
        for k in ("ic_mean", "ic_t", "top_avg_fwd", "uni_avg_fwd", "spread", "spread_t",
                  "hit_rate", "precision_at_k", "avg_carry_per_period",
                  "top_cagr_net_of_carry", "uni_cagr_net_of_carry", "top_sharpe_net", "uni_sharpe_net"):
            print(f"  {k:26}: {r.get(k)}")
        print("  verdict:", r.get("verdict"))
    print("\n=== CURRENT TOP SECTORS ===")
    ct = current_top()
    for H, ps in ct["picks"].items():
        print(f"  {H}m:", ", ".join(f"{p['sector']}({p['score']:+.3f})" for p in ps))
