"""Bake the grounded workflow outputs (staged JSON) into the project's data files,
normalizing sector names to the canonical taxonomy and reporting any mismatches.
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pakterm import config
from pakterm.sectors import SECTOR_NAMES

CANON = set(SECTOR_NAMES.values())

# common agent variants -> canonical
ALIAS = {
    "Oil & Gas Exploration Companies": "Oil & Gas Exploration",
    "Oil & Gas Marketing Companies": "Oil & Gas Marketing",
    "Commercial Bank": "Commercial Banks",
    "Banks": "Commercial Banks",
    "Power Generation": "Power Generation & Distribution",
    "Power": "Power Generation & Distribution",
    "Power Generation and Distribution": "Power Generation & Distribution",
    "Technology and Communication": "Technology & Communication",
    "Technology": "Technology & Communication",
    "Autos": "Automobile Assembler",
    "Automobile": "Automobile Assembler",
    "Automobiles": "Automobile Assembler",
    "Auto Assembler": "Automobile Assembler",
    "Automobile Parts": "Automobile Parts & Accessories",
    "Textile": "Textile Composite",
    "Textiles": "Textile Composite",
    "Fertiliser": "Fertilizer",
    "Fertilizers": "Fertilizer",
    "Pharma": "Pharmaceuticals",
    "Sugar": "Sugar & Allied",
    "Sugar & Allied Industries": "Sugar & Allied",
    "Refineries": "Refinery",
    "Steel": "Engineering",
    "Engineering (Steel)": "Engineering",
    "Cement Sector": "Cement",
    "Paper & Board": "Paper, Board & Packaging",
    "Paper, Board & Packaging ": "Paper, Board & Packaging",
    "Glass & Ceramics ": "Glass & Ceramics",
    "Vanaspati": "Vanaspati & Allied",
    "Real Estate": "Real Estate & Development",
    "REIT": "Real Estate Investment Trust",
    # shorthand labels fed to the grounding agent -> canonical
    "Auto Parts": "Automobile Parts & Accessories",
    "Cable & Electrical": "Cable & Electrical Goods",
    "Engineering(steel)": "Engineering",
    "Food & Personal Care": "Food & Personal Care Products",
    "Inv.Banks/Securities": "Inv. Banks / Inv. Cos. / Securities",
    "Paper/Board/Packaging": "Paper, Board & Packaging",
}


def norm(name):
    if name is None:
        return None
    n = str(name).strip()
    if n in CANON:
        return n
    if n in ALIAS:
        return ALIAS[n]
    # case-insensitive exact
    for c in CANON:
        if c.lower() == n.lower():
            return c
    return n  # unresolved -> keep, will be reported


def load(scr, name):
    return json.loads((scr / f"seed_{name}.json").read_text(encoding="utf-8"))


def main():
    scr = Path(sys.argv[1])
    unresolved = set()

    # 1) policy_rate.csv (authoritative rate step function)
    pol = load(scr, "policy")
    pev = sorted(pol["events"], key=lambda e: e["date"])
    with open(config.MACRO_DIR / "policy_rate.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "rate", "change_bps", "source"])
        for e in pev:
            w.writerow([e["date"], e["rate"], e.get("change_bps", ""), e.get("source", "")])
    print(f"policy_rate.csv: {len(pev)} decisions {pev[0]['date']}..{pev[-1]['date']} "
          f"({pev[0]['rate']}% -> {pev[-1]['rate']}%)")

    # 2) macro_monthly.csv  (+ policy_rate derived from the step function)
    mac = load(scr, "macro")
    import pandas as pd
    rows = mac["rows"]
    mdf = pd.DataFrame(rows)
    mdf["date"] = pd.to_datetime(mdf["month"], format="%Y-%m") + pd.offsets.MonthEnd(0)
    # derive month-end policy rate from authoritative events
    pr = pd.Series({pd.to_datetime(e["date"]): e["rate"] for e in pev}).sort_index()
    idx = mdf["date"]
    mdf["policy_rate"] = pr.reindex(pr.index.union(idx)).ffill().reindex(idx).values
    cols = ["date", "policy_rate", "cpi_yoy", "fx_reserves_sbp_bn", "remittances_bn",
            "current_account_mn", "pkr_usd", "brent_usd"]
    for c in cols:
        if c not in mdf:
            mdf[c] = None
    mdf[cols].to_csv(config.MACRO_DIR / "macro_monthly.csv", index=False)
    filled = {c: int(mdf[c].notna().sum()) for c in cols if c != "date"}
    print(f"macro_monthly.csv: {len(mdf)} months; non-null per field: {filled}")
    # provenance sidecar
    (config.MACRO_DIR / "provenance.json").write_text(
        json.dumps(mac.get("provenance", []), indent=2, ensure_ascii=False), encoding="utf-8")

    # 3) sector_graph.json (normalize sector names + link references)
    g = load(scr, "graph")
    for s in g.get("sectors", []):
        s["name"] = norm(s.get("name"))
        if s["name"] not in CANON:
            unresolved.add(("graph.sector", s["name"]))
        for key in ("upstream", "downstream"):
            s[key] = [norm(x) for x in s.get(key, [])]
    for ch in g.get("causal_chains", []):
        for a in ch.get("affected", []):
            a["sector"] = norm(a.get("sector"))
            if a["sector"] not in CANON:
                unresolved.add(("graph.chain", a["sector"]))
    (config.KNOWLEDGE_DIR / "sector_graph.json").write_text(
        json.dumps(g, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"sector_graph.json: {len(g.get('sectors', []))} sectors, "
          f"{len(g.get('causal_chains', []))} causal chains")

    # 4) events.json (normalize affected sector names)
    ev = load(scr, "events")
    for e in ev.get("events", []):
        e["sectors"] = [norm(x) for x in e.get("sectors", [])]
        for x in e["sectors"]:
            if x not in CANON:
                unresolved.add(("event", x))
    config.EVENTS_FILE.write_text(json.dumps(ev, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"events.json: {len(ev.get('events', []))} events")

    if unresolved:
        print("\n!! UNRESOLVED sector names (not in canonical taxonomy) — add to ALIAS:")
        for kind, name in sorted(unresolved):
            print(f"   [{kind}] {name!r}")
    else:
        print("\nAll sector names resolved to the canonical taxonomy.")


if __name__ == "__main__":
    main()
