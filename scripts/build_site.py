"""Full daily build for the deployed site: fetch latest PSX data, rebuild the
live strategy picks + bundle + terminal, and publish to docs/index.html (served
by GitHub Pages). The heavy futures meta-analysis (futures_result.json) is
committed and refreshed occasionally, not every day, to keep the daily build fast.

Run: python scripts/build_site.py            (full: fetch + rebuild)
     python scripts/build_site.py --no-fetch (skip download, rebuild only)
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(args):
    subprocess.run([PY, *args], cwd=str(ROOT), check=True)


def main():
    # --no-fetch means "do not hit the network", NOT "do not refresh the parquet".
    # fetch_psx.py --no-fetch still re-parses data/raw/ into the vendor parquet, which
    # matters whenever new raw files arrive WITHOUT a download -- e.g. pulled from the
    # daily CI commit. Skipping the parse there silently rebuilt the whole terminal on
    # a stale panel (parquet stuck at 2026-09-01 while raw/ already held Sep 2-4).
    if "--no-fetch" not in sys.argv:
        run([str(ROOT / "scripts" / "fetch_psx.py")])
    else:
        run([str(ROOT / "scripts" / "fetch_psx.py"), "--no-fetch"])
    # live strategy result (regime + picks + backtest) — the daily-changing part
    run(["-c", "import sys,json; sys.path.insert(0,'.'); "
                "from analysis import strategy as S; "
                "open('data/strategy_result.json','w',encoding='utf-8').write(json.dumps(S.build_result(),default=str)); "
                "print('strategy_result.json refreshed')"])
    # refresh macro/policy HEADLINES daily (guarded: keep last good file if the scrape
    # fails or returns nothing, so the news feed + sector-catalyst cross-ref stay current)
    try:
        # delegate to the single writer in refresh_macro so the never-clobber guard and
        # the last_ok/stale fields are applied identically here and in the weekly job.
        # This used to be a duplicated inline writer that omitted last_ok, so the tab
        # could not tell a stale set from a fresh one.
        subprocess.run([PY, "-c",
            "import sys; sys.path.insert(0,'.'); "
            "from scripts.refresh_macro import refresh_headlines; "
            "print(f'headlines on disk: {refresh_headlines()}')"],
            cwd=str(ROOT), check=False, timeout=120)
    except Exception as e:
        print(f"headlines refresh skipped: {type(e).__name__}")
    run(["-m", "terminal.bundle"])
    run(["-m", "terminal.build"])
    (ROOT / "docs").mkdir(exist_ok=True)
    shutil.copy(ROOT / "terminal" / "pak_terminal.html", ROOT / "docs" / "index.html")
    print("site built -> docs/index.html")


if __name__ == "__main__":
    main()
