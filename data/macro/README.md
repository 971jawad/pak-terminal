# Macro data — schema & provenance

Two curated, sourced, refreshable files feed the terminal. Every value must be
traceable to a public source; the fetchers under `scripts/` refresh them when
run in a network/browser-capable environment (SBP EasyData and stooq are bot-
walled to plain `curl`, so seeds are committed and refreshed opportunistically).

## `macro_monthly.csv`
One row per calendar month (`date` = month-end `YYYY-MM-DD`), columns (all optional):

| column | meaning | unit |
|---|---|---|
| policy_rate | SBP policy (target) rate, month-end | % |
| cpi_yoy | headline CPI inflation | % YoY |
| fx_reserves_sbp_bn | SBP-held FX reserves, month-end | USD bn |
| remittances_bn | workers' remittances (monthly inflow) | USD bn |
| current_account_mn | current account balance (+ = surplus) | USD mn |
| trade_balance_mn | goods trade balance | USD mn |
| pkr_usd | PKR per USD, interbank month-end | PKR |
| brent_usd | Brent crude, month average | USD/bbl |
| kse100 | KSE-100 index, month-end | index |
| us_10y | US 10y treasury yield, month-end | % |
| m2_growth_yoy | broad money growth | % YoY |

## `policy_rate.csv`
One row per SBP Monetary Policy Committee decision that changed (or reaffirmed)
the rate: `date, rate, change_bps, source`. `rate` is the level in %.

## Sources
- SBP policy rate & MPC statements: sbp.org.pk / EasyData (easydata.sbp.org.pk)
- CPI: Pakistan Bureau of Statistics (pbs.gov.pk)
- Reserves, remittances, current account, trade: SBP EasyData
- PKR/USD, Brent, KSE-100, US 10y: stooq / public market data
