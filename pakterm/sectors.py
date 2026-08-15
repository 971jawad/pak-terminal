"""PSX sector taxonomy.

The raw PSX daily files carry a numeric *sector code* (not a name). The mapping
below was reconstructed and VERIFIED against the actual data by identifying the
constituent tickers of each code (e.g. 0804 -> LUCK/DGKC/FCCL = Cement,
0807 -> HBL/MCB/UBL = Commercial Banks). Cross-checked against sarmaaya.pk,
which exposes the same codes (sarmaaya.pk/sector/0804 = Cement).

Codes 0801-0839 are the equity sector taxonomy. Non-08xx codes are exchange
*segments*, not economic sectors, and are excluded from sector analytics:
  36 / 3610  -> government debt (PIBs / GIS / sukuk, symbols P##...)
  41         -> index futures (KSE30-*, BKTI-*)
  40 / 0040  -> board/other/unclassified
  0837       -> ETFs (kept separate)
  ''         -> blank
"""

# code -> (short_name, verified?) ; verified=False means best-effort label
SECTOR_NAMES: dict[str, str] = {
    "0801": "Automobile Assembler",
    "0802": "Automobile Parts & Accessories",
    "0803": "Cable & Electrical Goods",
    "0804": "Cement",
    "0805": "Chemical",
    "0806": "Close-End Mutual Fund",
    "0807": "Commercial Banks",
    "0808": "Engineering",           # steel/engineering: ASTL, ISL, MUGHAL
    "0809": "Fertilizer",
    "0810": "Food & Personal Care Products",
    "0811": "Glass & Ceramics",
    "0812": "Insurance",
    "0813": "Inv. Banks / Inv. Cos. / Securities",
    "0814": "Jute",
    "0815": "Leasing Companies",
    "0816": "Leather & Tanneries",
    "0818": "Miscellaneous",         # diverse: SHFA, STPL, TRIPF, GAMON, UDL
    "0819": "Modarabas",
    "0820": "Oil & Gas Exploration",
    "0821": "Oil & Gas Marketing",
    "0822": "Paper, Board & Packaging",
    "0823": "Pharmaceuticals",
    "0824": "Power Generation & Distribution",
    "0825": "Refinery",
    "0826": "Sugar & Allied",
    "0827": "Synthetic & Rayon",
    "0828": "Technology & Communication",
    "0829": "Textile Composite",
    "0830": "Textile Spinning",
    "0831": "Textile Weaving",
    "0832": "Tobacco",
    "0833": "Transport",
    "0834": "Vanaspati & Allied",
    "0835": "Woollen",
    "0836": "Real Estate Investment Trust",
    "0837": "Exchange Traded Funds",
    "0838": "Real Estate & Development",   # provisional: property developers (TPLP/PACE/JVDC)
    "0839": "Textile (Apparel/Knitwear)",  # provisional: MSOT/INKL/IMAGE/STYLERS
}

# provisional labels we are less than certain about (constituents inferred)
PROVISIONAL = {"0838", "0839"}

# Non-08xx exchange segments (excluded from sector analytics).
NON_SECTOR_SEGMENTS = {"36", "3610", "40", "0040", "41", ""}

# Sectors that are funds/segments rather than operating businesses — excluded
# from the supply-chain / macro-linkage analytics (no real economic sector).
FUND_SECTORS = {"0806", "0815", "0819", "0837"}


def sector_name(code: str) -> str:
    return SECTOR_NAMES.get(str(code).strip(), f"[{code}]")


def is_equity_sector(code: str) -> bool:
    c = str(code).strip()
    return c in SECTOR_NAMES and c not in NON_SECTOR_SEGMENTS


def is_operating_sector(code: str) -> bool:
    """Real operating-business sectors (excludes funds/ETFs/leasing/modarabas)."""
    c = str(code).strip()
    return is_equity_sector(c) and c not in FUND_SECTORS and c != "0837"
