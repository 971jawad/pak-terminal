"""Assemble the full analytics bundle the terminal renders (pure data, no HTML).

Everything degrades gracefully: unseeded macro/graph/events yield empty sections
rather than errors, so the terminal is always buildable.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from pakterm import config, data
from analysis import regime, connections, events, sentiment, surges, mood, predictor, flows
from analysis import analysis_filter


def _series_xy(s: pd.Series, r=4):
    s = s.dropna()
    return {"x": [str(i.date()) if hasattr(i, "date") else str(i) for i in s.index],
            "y": [round(float(v), r) for v in s.values]}


def _load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _load_graph() -> dict:
    f = config.KNOWLEDGE_DIR / "sector_graph.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"sectors": [], "causal_chains": []}


def build_bundle(min_adv: float = config.MIN_ADV) -> dict:
    df = data.load_prices()
    mkt = data.market_index(min_adv)
    mkt_level = (1 + mkt).cumprod()
    mkt_month = data.to_monthly_returns(mkt)
    sec_daily = data.sector_daily_returns(min_adv)
    sec_month = data.to_monthly_returns(sec_daily)

    # sector performance snapshot
    def win_ret(s, n):
        s = s.dropna()
        return round(float(np.expm1(np.log1p(s).tail(n).sum())), 4) if len(s) else None
    sector_perf = []
    for s in sec_daily.columns:
        col = sec_daily[s]
        sector_perf.append({
            "sector": s,
            "r_1m": win_ret(col, 21), "r_3m": win_ret(col, 63),
            "r_12m": win_ret(col, 248),
            "vol_ann": round(float(col.dropna().tail(248).std() * np.sqrt(config.PPY)), 4)
            if col.dropna().shape[0] else None,
        })

    # cross-sector correlation (liquid, real sectors only)
    cc = connections.cross_sector_corr(min_adv)
    cc = cc.dropna(how="all").dropna(axis=1, how="all")
    corr = {"labels": list(cc.columns),
            "matrix": [[None if pd.isna(v) else round(float(v), 2) for v in row]
                       for row in cc.to_numpy()]}

    # cumulative sector index (monthly) for the biggest liquid sectors
    key_sectors = [p["sector"] for p in sorted(
        sector_perf, key=lambda p: (p["r_12m"] is None, -(p["r_12m"] or -9)))][:12]
    sec_cum = {}
    for s in key_sectors:
        cm = (1 + sec_month[s].dropna()).cumprod()
        if len(cm):
            sec_cum[s] = _series_xy(cm)

    macro = data.load_macro_monthly()
    macro_series = {c: _series_xy(macro[c]) for c in macro.columns
                    if macro[c].notna().any()} if not macro.empty else {}

    graph = _load_graph()
    smc = connections.sector_macro_corr(lag=0, min_adv=min_adv)                 # absolute
    smc_rel = connections.sector_macro_corr(lag=0, min_adv=min_adv, relative=True)  # market-adj
    smc1 = connections.sector_macro_corr(lag=1, min_adv=min_adv, relative=True)     # lead
    pve = connections.prior_vs_empirical(graph, min_adv)
    agree = {"all": connections.agreement_rate(pve, 0.0),
             "sig": connections.agreement_rate(pve, 2.0)}

    ev_by_type = events.by_type(min_adv)
    ev_hits = events.hit_rate(min_adv)
    ev_list = events.load_events()

    reg = regime.combined_view(min_adv)
    verify = regime.verify_edge(min_adv).reset_index()

    # --- mood, surges, predictor (price-derived) ---
    mood_now = mood.current_mood(min_adv)
    mood_bt = mood.mood_backtest(20, min_adv)
    mb = surges.multibaggers(3.0, top=25)
    recent = surges.recent_surgers(6, 15)
    bank = surges.bank_rate_thesis()
    surge_m = surges.surge_meta()
    dips = surges.dip_rebounds()
    shocks = surges.shock_response(min_adv)
    booms = surges.sector_booms()
    topgain = surges.top_gainers_by_year()
    pred = predictor.walkforward(min_adv)
    sec_base = predictor.sector_surge_base_rates(min_adv)

    # --- external research (baked from workflows) ---
    futures = _load_json(config.DATA / "futures_result.json", {"horizons": {}, "current": {}})
    strat = _load_json(config.DATA / "strategy_result.json", {})
    fundamentals = _load_json(config.DATA / "fundamentals.json", {"companies": []})
    sovereign = _load_json(config.DATA / "sovereign.json",
                           {"ratings": [], "external_debt": [], "imf_programs": [], "macro_annual": []})
    sources = _load_json(config.KNOWLEDGE_DIR / "data_sources.json", {"sources": []})

    bundle = {
        "meta": {
            "as_of": str(data.latest_date().date()),
            "n_symbols": int(df.symbol.nunique()),
            "n_months": int(len(mkt_month)),
            "min_adv": min_adv,
            "note": "Built on psx-quant's read-only price snapshot. Trend edge is "
                    "verified & out-of-sample; macro overlay, sector graph and "
                    "sentiment are context/priors, not fitted predictors.",
        },
        "regime": {
            "timing": reg["timing"], "macro": reg["macro"],
            "verify": verify.round(3).to_dict(orient="records"),
        },
        "index": {"level_daily": _series_xy(mkt_level),
                  "month_ret": _series_xy(mkt_month)},
        "sectors": {"perf": sector_perf, "cum": sec_cum, "corr": corr},
        "macro": {"series": macro_series},
        "connections": {
            "sector_macro_corr": smc.head(40).to_dict(orient="records") if not smc.empty else [],
            "sector_macro_corr_rel": smc_rel.head(40).to_dict(orient="records") if not smc_rel.empty else [],
            "sector_macro_corr_lag1": smc1.head(30).to_dict(orient="records") if not smc1.empty else [],
            "prior_vs_empirical": pve.astype(object).where(pve.notna(), None).to_dict(orient="records") if not pve.empty else [],
            "agreement": agree,
            "lead_lag": connections.lead_lag(min_adv).to_dict(orient="records")
            if len(sec_month) else [],
        },
        "events": {
            "by_type": ev_by_type.reset_index().to_dict(orient="records") if not ev_by_type.empty else [],
            "hit_rate": ev_hits.reset_index().to_dict(orient="records") if not ev_hits.empty else [],
            "list": (ev_list.assign(date=ev_list["date"].astype(str))
                     .to_dict(orient="records")) if not ev_list.empty else [],
        },
        "sentiment": {"by_sector": sentiment.sector_sentiment(),
                      "items": sentiment.load_news()},
        "graph": graph,
        "mood": {"current": mood_now, "backtest": mood_bt},
        "surges": {
            "multibaggers": mb.assign(name=mb.name.astype(str)).to_dict(orient="records") if not mb.empty else [],
            "recent": recent.to_dict(orient="records") if not recent.empty else [],
            "bank_thesis": bank,
            "surge_meta": surge_m,
            "dip_rebounds": dips,
            "shock_response": shocks.to_dict(orient="records") if not shocks.empty else [],
            "sector_booms": booms.to_dict(orient="records") if not booms.empty else [],
            "top_gainers_by_year": topgain.to_dict(orient="records") if not topgain.empty else [],
        },
        "predictor": {
            **{k: v for k, v in pred.items()},
            "sector_base_rates": sec_base.reset_index().to_dict(orient="records") if not sec_base.empty else [],
        },
        "fundamentals": fundamentals,
        "sovereign": sovereign,
        "sources": sources,
        "futures": futures,
        "flows": flows.summary(),
        "strategy": strat,
        "analysis_filter": analysis_filter.filter_result(min_adv),  # SEPARATE overlay
    }
    return bundle


def main():
    b = build_bundle()
    out = config.TERMINAL_DIR / "bundle.json"
    out.write_text(json.dumps(b, indent=None, default=str), encoding="utf-8")
    m = b["meta"]
    print(f"bundle: {m['n_symbols']} symbols, {m['n_months']} months, as of {m['as_of']}")
    print(f"  sectors_perf={len(b['sectors']['perf'])} corr_labels={len(b['sectors']['corr']['labels'])}")
    print(f"  macro_series={len(b['macro']['series'])} graph_sectors={len(b['graph'].get('sectors', []))} "
          f"chains={len(b['graph'].get('causal_chains', []))}")
    print(f"  events_by_type={len(b['events']['by_type'])} event_list={len(b['events']['list'])}")
    print(f"  sector_macro_corr={len(b['connections']['sector_macro_corr'])}")
    print(f"wrote {out} ({out.stat().st_size/1e3:.0f} KB)")


if __name__ == "__main__":
    main()
