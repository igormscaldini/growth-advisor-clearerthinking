"""Render theories_of_change.md to the HTML report next to this folder, and copy the Markdown to ~/Downloads."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from md_report import render_page  # noqa: E402  (shared page shell + base CSS in reports/md_report.py)

SRC = Path(__file__).parent / "theories_of_change.md"
OUT = Path(__file__).parent.parent / "year_end_appeal_theories_of_change_2026-10-19.html"
DOWNLOADS = Path.home() / "Downloads" / "CT_year-end_appeal_theories_of_change_2026-10-19.md"

EXTRA_CSS = "h2#sources + ol{font-size:14px;color:#444}\n"

if __name__ == "__main__":
    OUT.write_text(render_page(SRC.read_text(), "Year-end appeal: theories of change", EXTRA_CSS))
    shutil.copy(SRC, DOWNLOADS)
    print(OUT)
    print(DOWNLOADS)
