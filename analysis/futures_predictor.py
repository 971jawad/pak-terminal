"""Top-5 surger predictor for the FUTURES-ELIGIBLE universe — 1/2/3-month horizons.

Built to the honest standard the task demands:
  * Universe = PSX single-stock-futures-eligible names, POINT-IN-TIME (a stock is
    only in the universe in months it actually had a futures contract trading).
    No survivorship bias, no static current-list applied to history.
  * Features use ONLY trailing data (no look-ahead).
  * WALK-FORWARD with a PURGE/EMBARGO: to predict month t we train only on samples
    whose H-month forward label was fully realised on or before t (entry month
    <= t-H). This is essential — H>1 labels overlap, and without the purge the
    model trains on outcomes it shouldn't yet know.
  * Reported OUT-OF-SAMPLE: every prediction uses only prior information; we
    aggregate the concatenated walk-forward, and also summarise the last 18 months
    as a clean recent holdout.

Metrics per horizon: cross-sectional rank IC (+t-stat), top-5 basket forward
return vs the universe average and vs bottom-5, hit-rate, precision@5 (overlap
with the realised top-5), and a non-overlapping net-of-cost equity curve.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from pakterm import config, data

HORIZONS = (1, 2, 3)         # months
TOPK = 5
MIN_TRAIN_MONTHS = 30        # need history before the first OOS prediction
MIN_ADV = 20e6               # PKR liquidity floor (futures-grade)
COST_RT = 0.005              # round-trip cost per rebalance
FUT_ELIG_WINDOW = 3          # eligible if SSF traded within trailing N months

FEATURES = ["mom_1m", "mom_3m", "mom_6m", "mom_12m", "rev_1w", "vol_1m", "vol_3m",
            "dist_252h", "dist_20h", "dist_6mlow", "log_adv", "adv_growth",
            "turnover", "rel_str_3m", "rel_sec_3m", "maxup_1m", "upday_frac",
            "log_price", "month",
            # --- enriched "all data points" set ---
            "mom_accel", "vol_ratio", "amihud", "beta_60", "dd_6m", "sector_code",
            "rate_level", "rate_chg_3m", "cpi_yoy", "pkr_chg_3m", "oil_chg_3m",
            "mood_level"]


@lru_cache(maxsize=2)
def feature_panel(min_adv: float = MIN_ADV) -> pd.DataFrame:
    """Month-end feature rows for futures-eligible names + forward 1/2/3m labels."""
    df = data.load_prices().copy()
    g = df.groupby("symbol", sort=False)
    cl = g["cumlog"]
    for k, col in ((21, "mom_1m"), (63, "mom_3m"), (126, "mom_6m"), (252, "mom_12m"),
                   (5, "rev_1w")):
        df[col] = np.expm1(df.cumlog - cl.shift(k))
    df["vol_1m"] = g["r1"].transform(lambda s: s.rolling(20, min_periods=10).std())
    df["vol_3m"] = g["r1"].transform(lambda s: s.rolling(63, min_periods=30).std())
    rmax252 = cl.transform(lambda s: s.rolling(252, min_periods=60).max())
    rmax20 = cl.transform(lambda s: s.rolling(20, min_periods=10).max())
    rmin126 = cl.transform(lambda s: s.rolling(126, min_periods=40).min())
    df["dist_252h"] = np.expm1(df.cumlog - rmax252)
    df["dist_20h"] = np.expm1(df.cumlog - rmax20)
    df["dist_6mlow"] = np.expm1(df.cumlog - rmin126)
    adv120 = g["value"].transform(lambda s: s.rolling(120, min_periods=40).median())
    df["log_adv"] = np.log1p(df.adv_20)
    df["adv_growth"] = np.log1p(df.adv_20) - np.log1p(adv120)
    df["turnover"] = df.value / df.adv_20.replace(0, np.nan)
    df["maxup_1m"] = g["r1"].transform(lambda s: s.rolling(20, min_periods=10).max())
    df["upday_frac"] = g["r1"].transform(lambda s: (s > 0).rolling(20, min_periods=10).mean())
    df["log_price"] = np.log(df.close.clip(lower=0.1))
    df["month"] = df.date.dt.month

    liq = df[df.adv_20 > min_adv]
    mkt = liq.groupby("date")["r1"].mean()
    mcum = np.log1p(mkt).cumsum()
    df = df.merge(mkt.rename("mkt_r1"), left_on="date", right_index=True, how="left")
    df = df.merge(np.expm1(mcum - mcum.shift(63)).rename("mkt_mom_3m"),
                  left_on="date", right_index=True, how="left")
    df["rel_str_3m"] = df.mom_3m - df.mkt_mom_3m
    sec3 = df.groupby(["date", "sector"])["mom_3m"].transform("median")
    df["rel_sec_3m"] = df.mom_3m - sec3

    # --- enriched stock-specific microstructure features ---
    df["mom_accel"] = df.mom_1m - df.mom_3m / 3.0            # momentum picking up?
    df["vol_ratio"] = df.vol_1m / df.vol_3m.replace(0, np.nan)  # vol expansion
    il = df.r1.abs() / df.value.replace(0, np.nan)
    df["_il"] = il
    df["amihud"] = df.groupby("symbol", sort=False)["_il"].transform(
        lambda s: s.rolling(20, min_periods=10).mean())
    rmax126 = cl.transform(lambda s: s.rolling(126, min_periods=40).max())
    df["dd_6m"] = np.expm1(df.cumlog - rmax126)              # drawdown from 6m high
    # rolling beta to market (product-moment, 60d)
    gg = df.groupby("symbol", sort=False)
    er = gg["r1"].transform(lambda s: s.rolling(60, min_periods=30).mean())
    em = gg["mkt_r1"].transform(lambda s: s.rolling(60, min_periods=30).mean())
    df["_rm"] = df.r1 * df.mkt_r1
    df["_mm"] = df.mkt_r1 * df.mkt_r1
    erm = gg["_rm"].transform(lambda s: s.rolling(60, min_periods=30).mean())
    emm = gg["_mm"].transform(lambda s: s.rolling(60, min_periods=30).mean())
    df["beta_60"] = (erm - er * em) / (emm - em * em).replace(0, np.nan)

    # sample month-end rows
    df["ym"] = df.date.dt.to_period("M")
    lastday = df.groupby(["symbol", "ym"])["date"].transform("max")
    panel = df[df.date == lastday].copy()

    # forward H-month labels from the month-end cumlog grid
    grid = panel.pivot_table(index="ym", columns="symbol", values="cumlog")
    for H in HORIZONS:
        fwd = np.expm1(grid.shift(-H) - grid).stack().rename(f"fwd_{H}").reset_index()
        panel = panel.merge(fwd, on=["ym", "symbol"], how="left")

    # --- broadcast context features (help ranking only via interactions) ---
    codes = {name: i for i, name in enumerate(sorted(panel.sector_name.unique()))}
    panel["sector_code"] = panel.sector_name.map(codes).astype(float)
    mac = data.load_macro_monthly()
    if not mac.empty:
        mm = pd.DataFrame(index=mac.index.to_period("M"))
        mm["rate_level"] = mac["policy_rate"].values
        mm["rate_chg_3m"] = mac["policy_rate"].diff(3).values
        mm["cpi_yoy"] = mac["cpi_yoy"].values
        mm["pkr_chg_3m"] = mac["pkr_usd"].pct_change(3).values
        mm["oil_chg_3m"] = mac["brent_usd"].pct_change(3).values
        panel = panel.merge(mm, left_on="ym", right_index=True, how="left")
    try:
        from analysis.mood import mood_index
        mi = mood_index(min_adv)
        ml = mi.groupby(mi.index.to_period("M")).last().rename("mood_level")
        panel = panel.merge(ml, left_on="ym", right_index=True, how="left")
    except Exception:
        panel["mood_level"] = np.nan

    # POINT-IN-TIME futures eligibility (SSF traded in trailing FUT_ELIG_WINDOW months)
    fe = data.futures_eligible_months()
    elig = set()
    fe_by = {}
    for base, ym in fe.itertuples(index=False):
        fe_by.setdefault(base, set()).add(ym)
    def is_elig(sym, ym):
        s = fe_by.get(sym)
        if not s:
            return False
        return any((ym - k) in s for k in range(FUT_ELIG_WINDOW))
    panel["fut_elig"] = [is_elig(s, y) for s, y in zip(panel.symbol, panel.ym)]

    panel["eligible"] = (panel.fut_elig & (panel.adv_20 > min_adv)
                         & (panel.close >= 3) & panel.is_equity)
    return panel


def meta_analysis(H: int = 1, min_adv: float = MIN_ADV) -> list[dict]:
    """Standalone predictive power of EVERY metric: month-by-month cross-sectional
    rank IC with the forward H-month return, averaged, with a t-stat. This is the
    honest 'meta-analysis of all data points' — which single metrics actually rank
    future surgers, before any model. |t|>=2 ~ significant."""
    panel = feature_panel(min_adv)
    p = panel[panel.eligible].dropna(subset=[f"fwd_{H}"])
    rows = []
    for feat in FEATURES:
        ics = []
        for ym, grp in p.groupby("ym"):
            gg = grp.dropna(subset=[feat])
            if len(gg) >= 12 and gg[feat].nunique() > 3:
                ic = gg[feat].corr(gg[f"fwd_{H}"], method="spearman")
                if pd.notna(ic):
                    ics.append(ic)
        ics = np.array(ics)
        if len(ics) > 5:
            t = ics.mean() / (ics.std() + 1e-9) * np.sqrt(len(ics))
            rows.append({"feature": feat, "mean_ic": round(float(ics.mean()), 3),
                         "t": round(float(t), 2), "hit": round(float((ics > 0).mean()), 2),
                         "n_months": int(len(ics))})
    return sorted(rows, key=lambda r: -abs(r["t"]))


def factor_portfolio(H: int = 3, frac: float = 0.2, min_adv: float = MIN_ADV) -> dict:
    """Transparent, non-fitted factor TILT built from the meta-analysis.

    Composite = cross-sectional z-scores of well-established anomalies confirmed
    by the meta-analysis (momentum + proximity-to-high, MINUS volatility, beta,
    and recent-1-day-spike). No model is fit, so every month is genuinely OOS.
    We evaluate the top-quintile basket (a broad tilt), not the top-5 extremes —
    the honest test of whether the factors are usable.
    """
    panel = feature_panel(min_adv)
    p = panel[panel.eligible].copy()
    facs = {"mom_6m": 1, "dist_252h": 1, "vol_3m": -1, "beta_60": -1, "maxup_1m": -1}

    def z(s):
        return (s - s.mean()) / (s.std() + 1e-9)
    p["fscore"] = 0.0
    for f, sgn in facs.items():
        zc = p.groupby("ym")[f].transform(z).fillna(0.0) * sgn
        p["fscore"] = p["fscore"] + zc

    recs, eq = [], []
    next_reb = None
    for ym, grp in p.groupby("ym"):
        ev = grp.dropna(subset=[f"fwd_{H}", "fscore"])
        if len(ev) < 15:
            continue
        n = max(3, int(len(ev) * frac))
        top = ev.nlargest(n, "fscore"); bot = ev.nsmallest(n, "fscore")
        uni = float(ev[f"fwd_{H}"].mean())
        tr, brr = float(top[f"fwd_{H}"].mean()), float(bot[f"fwd_{H}"].mean())
        ic = float(ev["fscore"].corr(ev[f"fwd_{H}"], method="spearman"))
        recs.append({"ym": str(ym), "top": tr, "uni": uni, "bot": brr,
                     "spread": tr - uni, "ls": tr - brr, "ic": ic})
        if next_reb is None or ym >= next_reb:
            eq.append(tr - COST_RT); next_reb = ym + H
    if not recs:
        return {"H": H, "error": "no data"}
    r = pd.DataFrame(recs)
    ic_t = r.ic.mean() / (r.ic.std() + 1e-9) * np.sqrt(len(r))
    sp_t = r.spread.mean() / (r.spread.std() + 1e-9) * np.sqrt(len(r))
    ls_t = r.ls.mean() / (r.ls.std() + 1e-9) * np.sqrt(len(r))
    per_year = 12 / H
    eq = np.array(eq)
    ann = ((1 + eq).prod()) ** (per_year / max(1, len(eq))) - 1 if len(eq) else np.nan
    ann_uni = np.expm1(np.log1p(r.uni.values).mean() * per_year)
    reliable = (sp_t >= 2 and (r.spread > 0).mean() >= 0.55)
    return {
        "H": H, "frac": frac, "n_months": int(len(r)),
        "top_avg_fwd": round(float(r.top.mean()), 4),
        "universe_avg_fwd": round(float(r.uni.mean()), 4),
        "bottom_avg_fwd": round(float(r.bot.mean()), 4),
        "spread_top_minus_uni": round(float(r.spread.mean()), 4), "spread_t": round(float(sp_t), 2),
        "longshort_avg": round(float(r.ls.mean()), 4), "longshort_t": round(float(ls_t), 2),
        "ic_mean": round(float(r.ic.mean()), 3), "ic_t": round(float(ic_t), 2),
        "hit_rate": round(float((r.spread > 0).mean()), 3),
        "ann_top_net": None if np.isnan(ann) else round(float(ann), 3),
        "ann_universe": round(float(ann_uni), 3),
        "reliable": bool(reliable),
        "verdict": (f"USABLE TILT: top-quintile beats the universe by "
                    f"{r.spread.mean():+.1%}/period (t={sp_t:.1f}), long-short "
                    f"{r.ls.mean():+.1%} (t={ls_t:.1f}), {(r.spread>0).mean():.0%} hit."
                    if reliable else
                    f"weak/none: spread {r.spread.mean():+.1%} (t={sp_t:.1f}), "
                    f"LS {r.ls.mean():+.1%} (t={ls_t:.1f}) — factors real but not a robust portfolio tilt."),
    }


def surger_profile(H: int = 1, min_adv: float = MIN_ADV) -> dict:
    """Bottom-up 'surger autopsy': take the ACTUAL top-5 surgers of every period,
    look at their PRE-surge data points, and find what distinguished them from
    everyone else. Reported as a standardized mean difference (Cohen's d) per
    metric — the honest pattern-discovery the task asks for.

    This is descriptive (what past surgers looked like). Whether those patterns
    PREDICT out-of-sample is answered separately by walk_forward()/factor_portfolio()
    — here we just surface the DNA and let the effect sizes speak.
    """
    panel = feature_panel(min_adv)
    p = panel[panel.eligible].dropna(subset=[f"fwd_{H}"]).copy()
    p["is_surger"] = False
    for ym, g in p.groupby("ym"):
        p.loc[g.nlargest(TOPK, f"fwd_{H}").index, "is_surger"] = True
    S, N = p[p.is_surger], p[~p.is_surger]
    rows = []
    for f in FEATURES:
        sd = p[f].std()
        d = (S[f].mean() - N[f].mean()) / (sd + 1e-9)
        # per-period rank of the feature among that month's surgers (0-1, 1=top)
        rows.append({"feature": f, "surger_mean": round(float(S[f].mean()), 3),
                     "other_mean": round(float(N[f].mean()), 3),
                     "std_diff": round(float(d), 2)})
    rows.sort(key=lambda r: -abs(r["std_diff"]))
    sec = (S.sector_name.value_counts(normalize=True) * 100).round(1)
    return {
        "H": H, "n_surgers": int(len(S)),
        "surger_avg_fwd": round(float(S[f"fwd_{H}"].mean()), 3),
        "surger_median_fwd": round(float(S[f"fwd_{H}"].median()), 3),
        "surger_min_fwd": round(float(S[f"fwd_{H}"].min()), 3),
        "profile": rows,
        "top_sectors": [{"sector": k, "pct": float(v)} for k, v in sec.head(8).items()],
    }


def surge_drivers(H: int = 1, min_adv: float = MIN_ADV) -> dict:
    """Decompose the actual top-5 surges: how much was SECTOR BOOM vs idiosyncratic,
    and how much looks EARNINGS-driven (results-season timing + single-day pops)?

    Earnings proxy (no historical announcement dates available): PSX results
    cluster in Feb-Apr (annual/Q1), Aug-Sep (H1), Oct (Q3). An earnings pop is one
    big day; a momentum grind is many small ups. So we measure the single biggest
    day's share of the surge, the volume spike, and whether the big day fell in
    results season.
    """
    from analysis.connections import sector_monthly_returns
    panel = feature_panel(min_adv)
    p = panel[panel.eligible].dropna(subset=[f"fwd_{H}"]).copy()
    secm = sector_monthly_returns(min_adv)
    seccum = (1 + secm).cumprod()
    secfwd = seccum.shift(-H) / seccum - 1          # ym x sector forward return

    df = data.load_prices()
    dgs = {s: g[["date", "r1", "value"]].sort_values("date").reset_index(drop=True)
           for s, g in df.groupby("symbol", sort=False)}
    Hd = H * 21
    RESULTS_SEASON = {2, 3, 4, 8, 9, 10}
    rows = []
    for ym, g in p.groupby("ym"):
        if ym not in secfwd.index:
            continue
        sper = secfwd.loc[ym].dropna()
        thr = sper.quantile(0.75) if len(sper) else None
        top = g.nlargest(TOPK, f"fwd_{H}")
        for _, r in top.iterrows():
            fwd = r[f"fwd_{H}"]; sec = r["sector_name"]
            sfwd = secfwd.loc[ym, sec] if sec in secfwd.columns else np.nan
            sector_boom = bool(thr is not None and not np.isnan(sfwd) and sfwd >= thr)
            single_share = volspike = np.nan; peak_month = None
            gg = dgs.get(r["symbol"])
            if gg is not None and fwd and fwd > 0:
                i = int(gg.date.searchsorted(r["date"]))
                win = gg.iloc[i + 1:i + 1 + Hd]
                if len(win) > 3:
                    maxday = float(win.r1.max())
                    single_share = np.log1p(maxday) / np.log1p(fwd) if maxday > 0 else 0.0
                    prior = gg.iloc[max(0, i - 60):i].value.mean()
                    volspike = float(win.value.mean() / prior) if prior > 0 else np.nan
                    peak_month = int(win.loc[win.r1.idxmax(), "date"].month)
            rows.append({"fwd": fwd, "sfwd": sfwd, "sector_boom": sector_boom,
                         "single_share": single_share, "volspike": volspike,
                         "peak_month": peak_month, "sector": sec})
    R = pd.DataFrame(rows)
    Rv = R.dropna(subset=["single_share"])
    valid_s = R.dropna(subset=["sfwd"])
    return {
        "H": H, "n": int(len(R)),
        # --- sector-boom decomposition ---
        "pct_in_booming_sector": round(float(R.sector_boom.mean()), 3),
        "avg_surge": round(float(R.fwd.mean()), 3),
        "avg_sector_move": round(float(valid_s.sfwd.mean()), 3),
        "sector_share_of_surge": round(float(valid_s.sfwd.mean() / R.fwd.mean()), 3) if R.fwd.mean() else None,
        "idiosyncratic_share": round(float(1 - valid_s.sfwd.mean() / R.fwd.mean()), 3) if R.fwd.mean() else None,
        # --- earnings proxy ---
        "avg_single_day_share": round(float(Rv.single_share.mean()), 3),
        "pct_single_day_driven": round(float((Rv.single_share > 0.5).mean()), 3),
        "avg_volume_spike": round(float(Rv.volspike.median()), 2),
        "pct_peak_in_results_season": round(float(Rv.peak_month.dropna().isin(RESULTS_SEASON).mean()), 3),
        "results_season_baseline": round(len(RESULTS_SEASON) / 12, 3),
    }


def _reg():
    from sklearn.ensemble import HistGradientBoostingRegressor
    return HistGradientBoostingRegressor(max_depth=4, max_iter=300, learning_rate=0.05,
                                         min_samples_leaf=60, l2_regularization=1.0,
                                         random_state=42)


def walk_forward(H: int, min_adv: float = MIN_ADV) -> dict:
    panel = feature_panel(min_adv)
    p = panel[panel.eligible].dropna(subset=FEATURES).copy()
    months = sorted(p.ym.unique())
    recs, equity = [], []
    next_rebal = None
    for i, t in enumerate(months):
        if i < MIN_TRAIN_MONTHS:
            continue
        train = p[(p.ym <= (t - H))].dropna(subset=[f"fwd_{H}"])   # purge/embargo
        test = p[p.ym == t]
        if len(train) < 300 or len(test) < TOPK + 5:
            continue
        m = _reg()
        m.fit(train[FEATURES].to_numpy(np.float32), train[f"fwd_{H}"].to_numpy())
        test = test.assign(score=m.predict(test[FEATURES].to_numpy(np.float32)))
        top = test.nlargest(TOPK, "score")
        ev = test.dropna(subset=[f"fwd_{H}"])        # names whose outcome is realised
        if len(ev) >= TOPK + 5:
            uni = float(ev[f"fwd_{H}"].mean())
            top_ret = float(top[f"fwd_{H}"].mean())
            bot_ret = float(test.nsmallest(TOPK, "score")[f"fwd_{H}"].mean())
            ic = float(ev["score"].corr(ev[f"fwd_{H}"], method="spearman"))
            realized_top = set(ev.nlargest(TOPK, f"fwd_{H}").symbol)
            prec = len(set(top.symbol) & realized_top) / TOPK
            recs.append({"ym": str(t), "top_ret": top_ret, "uni": uni, "bot_ret": bot_ret,
                         "spread": top_ret - uni, "ic": ic, "prec": prec,
                         "picks": list(top.symbol)})
            # non-overlapping equity: only rebalance every H months
            if next_rebal is None or t >= next_rebal:
                equity.append(top_ret - COST_RT)
                next_rebal = t + H
    if not recs:
        return {"H": H, "error": "insufficient data"}
    r = pd.DataFrame(recs)
    ic_mean = r.ic.mean(); ic_t = ic_mean / (r.ic.std() + 1e-9) * np.sqrt(len(r))
    eq = np.array(equity)
    per_year = 12 / H

    # --- risk-adjusted / leverage-fair evaluation (non-overlapping periods) ---
    #   A strategy with a higher Sharpe can be levered to beat a higher-return one,
    #   and the geometric (compounded) return already penalises the -50%->+100%
    #   recovery asymmetry. So compare top-5 vs the equal-weight universe on Sharpe,
    #   CAGR and max drawdown, using non-overlapping H-month periods (net of cost).
    def _leg(series):
        s = np.array(series, dtype=float)
        if len(s) < 3:
            return {}
        eqc = np.cumprod(1 + s)
        cagr = eqc[-1] ** (per_year / len(s)) - 1
        vol = s.std(ddof=1) * np.sqrt(per_year)
        sharpe = (s.mean() * per_year) / (vol + 1e-9)
        dd = float((eqc / np.maximum.accumulate(eqc) - 1).min())
        return {"cagr": round(float(cagr), 3), "vol": round(float(vol), 3),
                "sharpe": round(float(sharpe), 2), "maxdd": round(float(dd), 3),
                "geo_per_period": round(float(eqc[-1] ** (1 / len(s)) - 1), 4)}
    idx = list(range(0, len(r), H))                 # non-overlapping entries
    rr = r.iloc[idx]
    legs = {"top5": _leg(rr.top_ret.values - COST_RT),
            "universe": _leg(rr.uni.values),
            "bottom5": _leg(rr.bot_ret.values - COST_RT)}
    lev = None
    if legs["top5"] and legs["universe"] and legs["universe"]["sharpe"] > 0:
        # leverage top-5 to the universe's volatility, then compare CAGR
        k = legs["universe"]["vol"] / (legs["top5"]["vol"] + 1e-9)
        lev = {"lever_to_uni_vol": round(float(k), 2),
               "top5_levered_cagr": round(float(rr.top_ret.sub(COST_RT).mul(k).mean() * per_year), 3),
               "beats_universe_riskadj": bool(legs["top5"]["sharpe"] > legs["universe"]["sharpe"])}
    ann = ((1 + eq).prod()) ** (per_year / max(1, len(eq))) - 1 if len(eq) else np.nan
    uni_eq = r.uni.values
    recent = r.tail(18)
    return {
        "H": H, "n_test_months": int(len(r)),
        "ic_mean": round(ic_mean, 3), "ic_t": round(float(ic_t), 2),
        "top5_avg_fwd": round(float(r.top_ret.mean()), 4),
        "universe_avg_fwd": round(float(r.uni.mean()), 4),
        "bottom5_avg_fwd": round(float(r.bot_ret.mean()), 4),
        "spread_top_minus_uni": round(float(r.spread.mean()), 4),
        "hit_rate_beat_uni": round(float((r.spread > 0).mean()), 3),
        "precision_at_5": round(float(r.prec.mean()), 3),
        "ann_return_net": None if np.isnan(ann) else round(float(ann), 3),
        "ann_universe": round(float(np.expm1(np.log1p(uni_eq).mean() * per_year)), 3),
        "recent18_spread": round(float(recent.spread.mean()), 4),
        "recent18_hit": round(float((recent.spread > 0).mean()), 3),
        "risk_adjusted": legs, "leverage": lev,
        "monthly": r[["ym", "top_ret", "uni", "spread", "ic", "prec"]].to_dict(orient="records"),
        "verdict": _verdict(ic_t, float((r.spread > 0).mean()), float(r.spread.mean())),
    }


def _verdict(ic_t, hit, spread):
    if ic_t >= 2 and hit >= 0.55 and spread > 0.005:
        return (f"RELIABLE-ish: rank IC t={ic_t:.1f}, top-5 beat the universe {hit:.0%} of "
                f"months by {spread:+.1%}/period on average. A real, measured edge.")
    if spread > 0 and ic_t >= 1:
        return (f"WEAK/SUGGESTIVE: IC t={ic_t:.1f}, {hit:.0%} hit, {spread:+.1%} spread. "
                f"Directionally positive but not robust enough to bet heavily.")
    return (f"NOT reliable: IC t={ic_t:.1f}, {hit:.0%} hit, {spread:+.1%} spread. "
            f"The metrics do not rank forward surgers out-of-sample.")


def feature_importance(H: int = 1, min_adv: float = MIN_ADV) -> list[dict]:
    from sklearn.inspection import permutation_importance
    panel = feature_panel(min_adv)
    p = panel[panel.eligible].dropna(subset=FEATURES + [f"fwd_{H}"])
    cut = sorted(p.ym.unique())[-18]
    tr, te = p[p.ym < cut], p[p.ym >= cut - H]
    te = te.dropna(subset=[f"fwd_{H}"])
    if len(tr) < 300 or len(te) < 100:
        return []
    m = _reg(); m.fit(tr[FEATURES].to_numpy(np.float32), tr[f"fwd_{H}"].to_numpy())
    pi = permutation_importance(m, te[FEATURES].to_numpy(np.float32),
                                te[f"fwd_{H}"].to_numpy(), n_repeats=5, random_state=0)
    imp = sorted(zip(FEATURES, pi.importances_mean), key=lambda x: -x[1])
    return [{"feature": f, "importance": round(float(v), 5)} for f, v in imp[:10]]


def current_picks(min_adv: float = MIN_ADV) -> dict:
    """Train on all purged data, predict the latest month -> top-5 per horizon."""
    panel = feature_panel(min_adv)
    p = panel[panel.eligible].dropna(subset=FEATURES).copy()
    last = max(p.ym.unique())
    out = {}
    for H in HORIZONS:
        train = p[(p.ym <= (last - H))].dropna(subset=[f"fwd_{H}"])
        cur = p[p.ym == last]
        if len(train) < 300 or len(cur) < TOPK:
            out[H] = []
            continue
        m = _reg(); m.fit(train[FEATURES].to_numpy(np.float32), train[f"fwd_{H}"].to_numpy())
        cur = cur.assign(score=m.predict(cur[FEATURES].to_numpy(np.float32)))
        top = cur.nlargest(TOPK, "score")
        out[H] = [{"symbol": r.symbol, "name": str(r["name"]),
                   "sector": r.sector_name, "score": round(float(r.score), 4),
                   "mom_3m": round(float(r.mom_3m), 3)} for _, r in top.iterrows()]
    return {"as_of_month": str(last), "picks": out}


def contextual_analysis(H: int = 1, min_adv: float = MIN_ADV) -> dict:
    """Investor-brain conditioning: does the top-5 pick beat the universe (and does
    it make money) in specific MACRO/POLICY REGIMES? We tag each walk-forward month
    with economically-motivated context — post-crash (buy-the-dip), easing cycle,
    risk-on, high-inflation, budget season — and split the OOS results by regime.

    Honest goal: find whether context is a reliable GATE. Two different things:
      * spread (top5 - universe): does context help SELECTION (which 5)?
      * top5 absolute return: does context help TIMING (when to be in at all)?
    """
    from analysis.regime import ensemble_signal
    panel = feature_panel(min_adv)
    p = panel[panel.eligible].copy()
    mkt = data.market_index(min_adv); lvl = (1 + mkt).cumprod()
    dd63 = lvl / lvl.rolling(63, min_periods=20).max() - 1     # drawdown from 3m peak
    sig = ensemble_signal(mkt)
    mac = data.load_macro_monthly(); mac.index = mac.index.to_period("M")
    cpi_med = mac["cpi_yoy"].median()
    months = sorted(p.ym.unique())
    recs = []
    for i, t in enumerate(months):
        if i < MIN_TRAIN_MONTHS:
            continue
        train = p[p.ym <= (t - H)].dropna(subset=[f"fwd_{H}"])
        test = p[p.ym == t]
        ev = test.dropna(subset=[f"fwd_{H}"])
        if len(train) < 300 or len(ev) < TOPK + 5:
            continue
        m = _reg(); m.fit(train[FEATURES].to_numpy(np.float32), train[f"fwd_{H}"].to_numpy())
        test = test.assign(score=m.predict(test[FEATURES].to_numpy(np.float32)))
        top = test.nlargest(TOPK, "score")
        edate = test.date.max()
        rc3 = float(mac["rate_chg_3m"].reindex([t]).iloc[0]) if "rate_chg_3m" not in mac and False else (
            float(mac["policy_rate"].reindex([t]).iloc[0] - mac["policy_rate"].reindex([t - 3]).iloc[0])
            if (t in mac.index and (t - 3) in mac.index) else np.nan)
        cpi = float(mac["cpi_yoy"].reindex([t]).iloc[0]) if t in mac.index else np.nan
        recs.append({
            "ym": str(t), "top": float(top[f"fwd_{H}"].mean()), "uni": float(ev[f"fwd_{H}"].mean()),
            "postdip": bool(float(dd63.asof(edate)) <= -0.10) if len(dd63) else False,
            "risk_on": bool(float(sig.asof(edate)) >= 0.5) if len(sig) else False,
            "easing": bool(rc3 < -0.25) if not np.isnan(rc3) else False,
            "high_infl": bool(cpi > cpi_med) if not np.isnan(cpi) else False,
            "budget": bool(t.month in (5, 6, 7)),
        })
    R = pd.DataFrame(recs)
    R["spread"] = R.top - R.uni
    if R.empty:
        return {"H": H, "error": "no data"}

    def stat(mask, label):
        s = R[mask]
        if len(s) < 4:
            return {"regime": label, "n": int(len(s)), "note": "too few"}
        sp_t = s.spread.mean() / (s.spread.std() + 1e-9) * np.sqrt(len(s))
        return {"regime": label, "n": int(len(s)),
                "top_avg": round(float(s.top.mean()), 4), "uni_avg": round(float(s.uni.mean()), 4),
                "spread": round(float(s.spread.mean()), 4), "spread_t": round(float(sp_t), 2),
                "hit": round(float((s.spread > 0).mean()), 2)}

    conds = [("ALL", R.index == R.index),
             ("post-dip (in >10% drawdown)", R.postdip), ("normal (not post-dip)", ~R.postdip),
             ("risk-ON", R.risk_on), ("risk-OFF", ~R.risk_on),
             ("easing cycle", R.easing), ("not easing", ~R.easing),
             ("high inflation", R.high_infl), ("low inflation", ~R.high_infl),
             ("budget season (May-Jul)", R.budget)]
    table = [stat(m, l) for l, m in conds]
    # gated strategy: only hold top-5 in a FAVOURABLE context (risk-on AND (post-dip OR easing))
    fav = R.risk_on & (R.postdip | R.easing)
    gated = stat(fav, "GATED: risk-on & (post-dip|easing)")
    gated_abs = round(float(R[fav].top.mean()), 4) if fav.sum() >= 4 else None
    return {"H": H, "n_months": int(len(R)), "by_regime": table,
            "gated": gated, "gated_top_abs": gated_abs,
            "ungated_top_abs": round(float(R.top.mean()), 4)}


def paper_trade(start: str = "2026-01", capital: float = 10000.0,
                use_timing: bool = False, min_adv: float = MIN_ADV) -> dict:
    """Concrete paper-trade from `start` to data end: each rebalance the model
    (trained purged, no look-ahead) picks the top-5 futures-eligible names, GATED
    by the timing signal (RISK-OFF -> hold cash at the T-bill rate). Equal-weight,
    profits reinvested, net of 0.5% round-trip cost + policy-rate futures carry.
    Non-overlapping per horizon. TINY sample — this is what THIS window did, not
    proof of edge (the full OOS test found none)."""
    from analysis.regime import ensemble_signal
    panel = feature_panel(min_adv)
    p = panel[panel.eligible].copy()
    months = sorted(p.ym.unique())
    start_p = pd.Period(start, "M")
    mkt = data.market_index(min_adv)
    sig = ensemble_signal(mkt)
    mac = data.load_macro_monthly(); mac.index = mac.index.to_period("M")

    out = {}
    for H in HORIZONS:
        # non-overlapping entry months with a realised forward-H return
        entries = [m for m in months if m >= start_p and
                   p[(p.ym == m)][f"fwd_{H}"].notna().any()]
        entries = entries[::H]
        equity = capital; legs = []
        for m in entries:
            edate = p[p.ym == m].date.max()
            expo = float(sig.asof(edate)) if len(sig) else 0.0
            risk_on = True if not use_timing else (expo >= 0.5)
            rate = float(mac["policy_rate"].reindex([m]).iloc[0]) if m in mac.index else 11.0
            carry = (rate / 100) * (H / 12)
            if risk_on:
                # HGB handles NaN features natively -> only require the label for training
                train = p[p.ym <= (m - H)].dropna(subset=[f"fwd_{H}"])
                cur = p[p.ym == m]
                if len(train) < 200 or len(cur) < TOPK:
                    continue
                mdl = _reg(); mdl.fit(train[FEATURES].to_numpy(np.float32), train[f"fwd_{H}"].to_numpy())
                cur = cur.assign(score=mdl.predict(cur[FEATURES].to_numpy(np.float32)))
                top = cur.nlargest(TOPK, "score")
                gross = float(top[f"fwd_{H}"].mean())
                ret = gross - 0.005 - carry
                picks = [{"sym": r.symbol, "ret": round(float(r[f"fwd_{H}"]), 3)} for _, r in top.iterrows()]
                mode = "TOP5 (risk-on)"
            else:
                ret = carry            # cash at T-bill
                picks = []; gross = None; mode = "CASH (risk-off)"
            equity *= (1 + ret)
            legs.append({"month": str(m), "mode": mode, "exposure": round(expo, 2),
                         "gross": None if gross is None else round(gross, 3),
                         "net_ret": round(ret, 3), "equity": round(equity, 0), "picks": picks})
        out[H] = {"legs": legs, "n_trades": len(legs),
                  "final": round(equity, 0), "profit": round(equity - capital, 0),
                  "return_pct": round((equity / capital - 1) * 100, 1)}
    combined_final = sum(out[H]["final"] for H in HORIZONS)
    return {"start": start, "capital_each": capital, "per_horizon": out,
            "combined_invested": capital * len(HORIZONS),
            "combined_final": round(combined_final, 0),
            "combined_profit": round(combined_final - capital * len(HORIZONS), 0),
            "combined_return_pct": round((combined_final / (capital * len(HORIZONS)) - 1) * 100, 1)}


def run_all(min_adv: float = MIN_ADV) -> dict:
    res = {H: walk_forward(H, min_adv) for H in HORIZONS}
    return {"horizons": res, "importance_1m": feature_importance(1, min_adv),
            "meta_analysis": {H: meta_analysis(H, min_adv) for H in (1, 3)},
            "surger_dna": {H: surger_profile(H, min_adv) for H in (1, 3)},
            "factor_tilt": {H: factor_portfolio(H, 0.2, min_adv) for H in HORIZONS},
            "current": current_picks(min_adv),
            "universe_now": len(data.eligible_now()),
            "eligible_sample": data.eligible_now()[:40]}


if __name__ == "__main__":
    import json
    for H in HORIZONS:
        r = walk_forward(H)
        print(f"\n=== HORIZON {H} MONTH — walk-forward OOS ({r.get('n_test_months')} months) ===")
        for k in ("ic_mean", "ic_t", "top5_avg_fwd", "universe_avg_fwd", "bottom5_avg_fwd",
                  "spread_top_minus_uni", "hit_rate_beat_uni", "precision_at_5",
                  "ann_return_net", "ann_universe", "recent18_spread", "recent18_hit"):
            print(f"  {k:24}: {r.get(k)}")
        print("  verdict:", r.get("verdict"))
    print("\n=== FEATURE IMPORTANCE (1m) ===")
    for f in feature_importance(1):
        print(f"  {f['feature']:14} {f['importance']:+.5f}")
    print("\n=== CURRENT TOP-5 PICKS ===")
    cp = current_picks()
    for H, picks in cp["picks"].items():
        print(f"  {H}m:", ", ".join(f"{p['symbol']}({p['score']:+.3f})" for p in picks))
