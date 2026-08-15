"""News + 5-tier sentiment scaffold.

Honest framing: a real-time DECISION AID, not a backtestable edge on this 7-year
history. News flow is sparse, unstructured, and unavailable as clean history, so
we do not claim it predicts returns. What this module provides:

  1. a 5-tier source/impact taxonomy that weights how much a headline matters,
  2. a headline -> PSX sector linker (keyword + ticker-name matching),
  3. an LLM tagging contract (prompt + schema) to classify sentiment at ingest,
  4. a tier-weighted sector-sentiment aggregation for the terminal,
  5. a small illustrative seed so the terminal renders live.

Tiers (1 = highest credibility/impact):
  T1 official   — SBP / MoF / SECP / PSX notice / company material disclosure
  T2 wire/press — Reuters, Bloomberg, Business Recorder, Dawn Business
  T3 mainstream — general national news desks
  T4 analyst    — brokerage notes, research desks (directional but interested)
  T5 social     — X/forums/rumor (noisy, discount heavily)
"""
from __future__ import annotations

import json
import re

from pakterm import config
from pakterm.sectors import SECTOR_NAMES

TIER_WEIGHT = {1: 1.0, 2: 0.8, 3: 0.55, 4: 0.4, 5: 0.15}

# keyword -> sector name (extend freely; drives the headline linker)
SECTOR_KEYWORDS: dict[str, list[str]] = {
    "Cement": ["cement", "clinker", "construction", "housing", "psdp", "coal"],
    "Commercial Banks": ["bank", "deposit", "advance", "nim", "monetary policy",
                          "policy rate", "spread", "sbp rate"],
    "Fertilizer": ["fertiliz", "urea", "dap", "gas feedstock", "gidc", "sona", "ffc"],
    "Oil & Gas Exploration": ["exploration", "e&p", "gas discovery", "oil field",
                              "ogdc", "ppl", "circular debt"],
    "Oil & Gas Marketing": ["ogra", "fuel price", "petrol price", "opl", "pso",
                            "lng", "furnace oil"],
    "Refinery": ["refiner", "deemed duty", "brownfield", "crude", "hsd"],
    "Power Generation & Distribution": ["ipp", "power", "electricity", "tariff",
                                        "circular debt", "capacity payment", "nepra"],
    "Automobile Assembler": ["auto", "car sales", "ckd", "vehicle", "ev policy",
                             "indus motor", "honda", "suzuki", "tractor"],
    "Textile Composite": ["textile", "cotton", "yarn", "exports", "gsp", "apparel"],
    "Technology & Communication": ["it exports", "software", "tech", "telecom",
                                   "systems limited", "fintech", "data centre"],
    "Pharmaceuticals": ["pharma", "drug price", "drap", "api import"],
    "Sugar & Allied": ["sugar", "cane", "crushing", "support price"],
    "Chemical": ["pvc", "petrochemical", "pta", "chemical"],
    "Engineering": ["steel", "rebar", "long steel", "scrap", "engineering"],
}


def link_sectors(headline: str) -> list[str]:
    """Best-effort mapping of a headline to affected PSX sectors."""
    h = headline.lower()
    hits = []
    for sector, kws in SECTOR_KEYWORDS.items():
        if any(re.search(r"\b" + re.escape(k), h) for k in kws):
            hits.append(sector)
    return hits


# ---- LLM tagging contract (used at ingest by a live pipeline) ---------------

LLM_TAGGING_SCHEMA = {
    "type": "object",
    "required": ["tier", "sentiment", "sectors", "rationale"],
    "properties": {
        "tier": {"type": "integer", "minimum": 1, "maximum": 5},
        "sentiment": {"type": "number", "minimum": -1, "maximum": 1},
        "sectors": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
}

LLM_TAGGING_PROMPT = (
    "You are a Pakistan equity news analyst. Classify the headline for a PSX "
    "terminal. Return: tier (1 official/SBP/regulator/company disclosure ... 5 "
    "social/rumor), sentiment in [-1,+1] for the AFFECTED PSX SECTORS (not the "
    "country mood), the affected PSX sector names from the fixed taxonomy, and a "
    "one-line rationale grounded in the transmission channel (e.g. 'rate cut -> "
    "cheaper auto financing + construction demand -> +Autos,+Cement').\n\n"
    "Valid sectors: " + ", ".join(sorted(set(SECTOR_NAMES.values()))) + "\n\nHeadline: "
)


def load_news() -> list[dict]:
    f = config.NEWS_DIR / "news.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8")).get("items", [])
    return _SEED


def sector_sentiment(items: list[dict] | None = None) -> dict[str, dict]:
    """Tier-weighted average sentiment per sector across the news items."""
    items = items if items is not None else load_news()
    acc: dict[str, list[float]] = {}
    wsum: dict[str, float] = {}
    for it in items:
        w = TIER_WEIGHT.get(int(it.get("tier", 3)), 0.5)
        s = float(it.get("sentiment", 0.0))
        for sec in it.get("sectors") or link_sectors(it.get("headline", "")):
            acc.setdefault(sec, 0.0)
            acc[sec] += w * s
            wsum[sec] = wsum.get(sec, 0.0) + w
    return {sec: {"score": round(acc[sec] / wsum[sec], 3), "weight": round(wsum[sec], 2)}
            for sec in acc}


# Illustrative seed (clearly synthetic examples, so the terminal renders before a
# live feed is wired). Replace via data/news/news.json.
_SEED = [
    {"date": "2026-08-12", "headline": "SBP holds policy rate at 11%, cites easing inflation",
     "source": "Business Recorder", "tier": 2, "sentiment": 0.3,
     "sectors": ["Commercial Banks", "Cement", "Automobile Assembler"],
     "rationale": "stable-to-lower rates support credit-sensitive sectors"},
    {"date": "2026-08-11", "headline": "Cement dispatches rise on public housing push",
     "source": "Dawn Business", "tier": 2, "sentiment": 0.5, "sectors": ["Cement"],
     "rationale": "volume growth + construction demand"},
    {"date": "2026-08-10", "headline": "IT exports hit record on data-centre demand",
     "source": "PSEB", "tier": 1, "sentiment": 0.6,
     "sectors": ["Technology & Communication"], "rationale": "USD revenue tailwind"},
    {"date": "2026-08-08", "headline": "Rumor of gas tariff hike weighs on fertilizer",
     "source": "X/social", "tier": 5, "sentiment": -0.4, "sectors": ["Fertilizer"],
     "rationale": "feedstock cost risk (unconfirmed)"},
]


if __name__ == "__main__":
    print("=== illustrative sector sentiment (tier-weighted) ===")
    for sec, v in sorted(sector_sentiment().items(), key=lambda x: -x[1]["score"]):
        print(f"  {sec:32s} {v['score']:+.3f}  (w={v['weight']})")
    print("\nlink test:", link_sectors("SBP cuts rate; cement and auto financing to ease"))
