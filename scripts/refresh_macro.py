"""Weekly macro refresh — keeps the terminal's macro/policy context current
without any paid key. Two sources, both graceful on failure:

  * World Bank API (keyless, reliable): latest annual macro numbers for Pakistan
    (inflation, GDP growth, current account, reserves, etc.).
  * ProfitPakistan (best-effort): recent macro/policy/geopolitical HEADLINES —
    the news layer, since SBP/most aggregators block bots and the good structured
    macro sources need a key. Headlines are awareness, with any numbers in-text.

Writes data/macro/worldbank.json and data/macro/headlines.json. Run weekly by CI.
"""
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "macro"
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}

WB_INDICATORS = {
    "inflation_cpi_annual_pct": "FP.CPI.TOTL.ZG",
    "gdp_growth_pct": "NY.GDP.MKTP.KD.ZG",
    "current_account_pctgdp": "BN.CAB.XOKA.GD.ZS",
    "reserves_usd": "FI.RES.TOTL.CD",
    "policy_lending_rate_pct": "FR.INR.LEND",
    "pop_millions": "SP.POP.TOTL",
}


def world_bank() -> dict:
    out = {}
    for name, ind in WB_INDICATORS.items():
        try:
            r = requests.get(
                f"https://api.worldbank.org/v2/country/PAK/indicator/{ind}",
                params={"format": "json", "date": "2018:2026", "per_page": "20"},
                headers=UA, timeout=25)
            data = r.json()
            series = [{"year": d["date"], "value": d["value"]}
                      for d in (data[1] or []) if d.get("value") is not None]
            series.sort(key=lambda x: x["year"], reverse=True)
            if series:
                out[name] = {"latest_year": series[0]["year"], "latest": round(series[0]["value"], 2),
                             "series": series[:8]}
        except Exception as e:
            out[name] = {"error": type(e).__name__}
    return out


KEY = re.compile(r"inflation|policy rate|interest rate|\bSBP\b|monetary|rupee|dollar|IMF|budget|"
                 r"\bGDP\b|current account|remittance|reserves?|deficit|tariff|oil price|"
                 r"circular debt|fiscal|T-bill|bond|geopolit|Iran|India|Afghan|sanction", re.I)


def _titles_from(html: str) -> list[str]:
    # anchor text and heading text, kept if macro-relevant
    cand = re.findall(r">([A-Z][A-Za-z0-9 ,'’:%\$\.\-\(\)]{28,110})<", html)
    seen, out = set(), []
    for t in cand:
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) < 28 or t in seen or not KEY.search(t):
            continue
        seen.add(t)
        out.append(t)
    return out


def headlines() -> list[str]:
    urls = ["https://profit.pakistantoday.com.pk/",
            "https://profit.pakistantoday.com.pk/category/economy/",
            "https://profit.pakistantoday.com.pk/category/markets/"]
    found = []
    for u in urls:
        try:
            r = requests.get(u, headers=UA, timeout=25)
            if r.status_code == 200:
                found += _titles_from(r.text)
        except Exception:
            pass
    seen, out = set(), []
    for t in found:
        if t not in seen:
            seen.add(t); out.append(t)
    return out[:40]


def main():
    wb = world_bank()
    (OUT / "worldbank.json").write_text(json.dumps(wb, indent=None), encoding="utf-8")
    hl = headlines()
    from datetime import date
    (OUT / "headlines.json").write_text(
        json.dumps({"as_of": date.today().isoformat(), "source": "profit.pakistantoday.com.pk",
                    "headlines": hl}, indent=None), encoding="utf-8")
    print(f"world bank: {sum(1 for v in wb.values() if 'latest' in v)}/{len(wb)} indicators")
    for k, v in wb.items():
        if "latest" in v:
            print(f"  {k}: {v['latest']} ({v['latest_year']})")
    print(f"headlines: {len(hl)} macro-relevant")
    for h in hl[:12]:
        print("  -", h[:90])


if __name__ == "__main__":
    main()
