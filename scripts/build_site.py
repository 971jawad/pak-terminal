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
    if "--no-fetch" not in sys.argv:
        run([str(ROOT / "scripts" / "fetch_psx.py")])
    # live strategy result (regime + picks + backtest) — the daily-changing part
    run(["-c", "import sys,json; sys.path.insert(0,'.'); "
                "from analysis import strategy as S; "
                "open('data/strategy_result.json','w',encoding='utf-8').write(json.dumps(S.build_result(),default=str)); "
                "print('strategy_result.json refreshed')"])
    run(["-m", "terminal.bundle"])
    run(["-m", "terminal.build"])
    (ROOT / "docs").mkdir(exist_ok=True)
    shutil.copy(ROOT / "terminal" / "pak_terminal.html", ROOT / "docs" / "index.html")
    print("site built -> docs/index.html")


if __name__ == "__main__":
    main()
