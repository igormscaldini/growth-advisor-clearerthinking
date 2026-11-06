"""Renders og.png, the 1200x630 image social networks show when the astrology prize page is shared.

The card is og_card.html (it reads the prize amount and the pass mark from logic.js). Rerun this after
changing either file. The screenshot helper is the ct-infographic kit's, so Chrome and the fonts are
handled the same way as for every other CT graphic.

Run:  .venv/bin/python landing_pages/astrology_prize/build_og.py
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / ".claude/skills/ct-infographic/scripts"))
import ct_infographic as kit  # noqa: E402

CARD = HERE / "og_card.html"
PNG = HERE / "og.png"
SIZE = (1200, 630)

if __name__ == "__main__":
    # export() writes the HTML it is given before taking the screenshot; handing it the card's own
    # text leaves the file as it was.
    kit.export(CARD.read_text(encoding="utf-8"), CARD, PNG, width=SIZE[0], height=SIZE[1], scale=1)
    print(f"wrote {PNG} ({PNG.stat().st_size / 1024:.0f} KB)")
