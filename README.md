# Pakistan Macro-Financial Terminal

A Bloomberg-style terminal for Pakistan: PSX stocks, sectors and their supply-chain
interconnections, SBP/macro data, global-shock exposure, dated policy/event studies,
a market-regime signal, and a 5-tier news-sentiment feed — in one screen.

Built as a **separate project on top of** [`psx-quant`](../psx-quant). It consumes
that project's cleaned 7-year PSX price panel **read-only** (a snapshot lives in
`data/vendor/`) and **never modifies it**.

## The honest thesis (read this first)

This project deliberately refuses the trap that killed four earlier stock-pickers:
fitting a "monthly predictor" on ~85 monthly data points. With that little history,
rich macro/news breadth produces beautiful backtests that die live. So the terminal
separates what is **validated** from what is **context**:

| Layer | Status | What it is |
|---|---|---|
| **Market-timing regime** | ✅ verified, out-of-sample, cost-surviving | Trend-following on the liquid index. Sharpe ~1.15 → ~1.7, max drawdown ~−42% → ~−16–23%. The one real edge, carried from psx-quant. |
| **Sector interconnection graph** | 🧭 curated prior | Hand-built supply-chain / macro-sensitivity map (economic logic + cited facts), not fitted. |
| **Sector × macro correlations** | 📊 descriptive | Real correlations with sample size + t-stats; anything \|t\|<2 flagged not-significant. |
| **Event studies** | 📊 descriptive | Sector abnormal returns around dated events, aggregated by *type* (single events are N=1). |
| **News 5-tier sentiment** | 📰 real-time aid | Not backtestable on this history; a decision aid, honestly labelled. |

The terminal shows *curated prior vs. measured correlation side by side*, so you see
where the story agrees with the data instead of trusting either blindly.

## Layout

```
pakterm/         core: config, sector taxonomy (verified codes), PSX data adapter, macro loader
analysis/        regime (the edge + macro overlay), connections (correlations),
                 events (event studies), sentiment (5-tier news)
knowledge/       sector_graph.json — curated supply-chain / interconnection map
data/vendor/     read-only PSX price snapshot from psx-quant
data/macro/      curated + refreshable macro series (policy rate, CPI, reserves, PKR, oil…)
data/events.json dated policy/macro event catalog
terminal/        bundle.py (assemble analytics) + build.py (render the dashboard)
scripts/         refresh.py (mirror prices; best-effort macro fetch)
```

## Run

```bash
# uses psx-quant's venv (pandas/numpy/pyarrow/scikit-learn already installed)
PY=../psx-quant/.venv/Scripts/python.exe

$PY -m analysis.regime         # verified trend edge + today's RISK-ON/OFF + macro overlay
$PY -m analysis.connections    # sector×macro + cross-sector correlations (with t-stats)
$PY -m analysis.events         # event studies by type
$PY -m analysis.sentiment      # 5-tier sector sentiment
$PY -m terminal.bundle         # assemble terminal/bundle.json
$PY -m terminal.build          # render terminal/pak_terminal.html
$PY -m scripts.refresh         # mirror PSX snapshot; attempt macro refresh
```

## Data provenance & freshness

- **Prices**: PSX daily (dps.psx.com.pk) via psx-quant, 2019-07 → present, ~711 tradable
  symbols, 37 equity sectors (codes verified against constituents).
- **Macro**: curated from SBP / PBS / market data with per-field sources
  (`data/macro/README.md`). Live fetch is best-effort — SBP EasyData and stooq are
  bot-walled to plain requests, so seeds are committed and refreshed opportunistically.
  Every macro value is sourced or flagged as interpolated.
