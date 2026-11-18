"""Re-flow the Clearer Thinking Plus perks banner without the Life-Changing Questions deck tile.

The banner (List_of_perks_2x.png, shown at the end of the Life-Changing Questions tool and of the Ultimate
Personality Test report) is a 3 x 3 grid of perk tiles. Nothing is redrawn here: tiles are moved pixel for pixel,
so the icons, the lettering and the shadows stay the designer's. The original is kept beside this script because
the CDN copy is meant to be replaced by the output.

    python reports/ct_plus_perks_banner_2026-11-18_src/build.py

writes the PNGs to ~/Downloads and a before/after preview to reports/ct_plus_perks_banner_2026-11-18.html.

How it works
- Row 1 is untouched. Row 2 keeps its three cards and only their insides are swapped (same shape, so the shadows
  around them are already right).
- Row 3 has fewer tiles, centred. `compose_row` rebuilds it by cutting the band into vertical pieces (outer edge,
  tile body, the gap between two tiles) and joining the ones needed, so every edge keeps its real shadow.
- Between rows 2 and 3 the shadows of both rows overlap. Shadows are treated as additive darkening of the
  background ("deficits"): the faint upper shadow of the old row 3 is taken out and the one of the new row 3 put in.
"""
import base64
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from md_report import timestamp  # noqa: E402

ORIGINAL = HERE / "original_List_of_perks_2x.png"
PREVIEW = HERE.parent / "ct_plus_perks_banner_2026-11-18.html"
DOWNLOADS = Path.home() / "Downloads"

# Geometry of the original, measured from its pixels.
BG = 250                      # background grey; shadows are darker, cards are 255
X = (135, 417, 699)           # first column of each card
W = 257                       # card width
PITCH = X[1] - X[0]           # 282
ROW_TOP = (445, 797, 1148)    # first fully white row of each card row
CARD_H = 327                  # fully white rows per card
ROW_STEP = ROW_TOP[2] - ROW_TOP[1]   # 351, row 2 -> row 3
STRIP = 24                    # left/right margin of a card that never holds content (wider than the corner radius)
INSET = 6                     # rows left alone at the top and bottom of a card when its inside is swapped
GAP_TOP = ROW_TOP[1] + CARD_H + 1    # 1125, first row below row 2's anti-aliased bottom edge
TOP_SHADOW_SHIFT = 704        # row 3's upper shadow has the shape of row 1's: rows 421..443 -> 1125..1147

# Tiles of the original as (row, column).
COACHING, COGNITIVE, PDF = (0, 0), (0, 1), (0, 2)
DECK, PODCASTS, BONUS = (1, 0), (1, 1), (1, 2)
WRAP_UP, EARLY_ACCESS, TSHIRT = (2, 0), (2, 1), (2, 2)


def compose_row(band, keep):
    """Return `band` (rows x width x channels of pixel values, one 3-tile row with its shadows) holding only the
    tiles whose column index is in `keep`, in that order, centred, each edge with the shadow the original draws
    there. The freed space is filled with the background grey."""
    pieces = [band[:, :X[0] + STRIP]]                                  # canvas edge .. left margin of a card
    for n, col in enumerate(keep):
        if n:
            g = keep[n - 1] if col == keep[n - 1] + 1 else 0           # the gap the two tiles already share, if any
            pieces.append(band[:, X[g] + W - STRIP:X[g + 1] + STRIP])  # right margin + gap + left margin
        pieces.append(band[:, X[col] + STRIP:X[col] + W - STRIP])      # the tile's own content
    pieces.append(band[:, X[2] + W - STRIP:])                          # right margin of a card .. canvas edge
    row = np.concatenate(pieces, axis=1)
    out = np.full_like(band, BG)
    left = (band.shape[1] - row.shape[1]) // 2
    out[:, left:left + row.shape[1]] = row
    return out


def card_columns(n_tiles):
    """First column of each card in a centred row of `n_tiles`."""
    left = X[0] + PITCH * (3 - n_tiles) // 2
    return [left + PITCH * n for n in range(n_tiles)]


def _inside(tile):
    """Slices of a card's inside: the columns between its two margins, minus INSET rows at the top and bottom.
    Every card is plain white around that rectangle, and it stays clear of the rounded corners."""
    r, c = tile
    return (slice(ROW_TOP[r] + INSET, ROW_TOP[r] + CARD_H - INSET), slice(X[c] + STRIP, X[c] + W - STRIP))


def reflow(rgb, row2, row3):
    """rgb: the original as an int array (height x width x 3). row2: the three tiles to show in row 2.
    row3: the row-3 tiles to keep (any number, centred). Returns the new image, same size."""
    rgb = rgb.astype(int)
    new = rgb.copy()

    # Row 2: same cards, new insides.
    for col, tile in enumerate(row2):
        new[_inside((1, col))] = rgb[_inside(tile)]

    keep = [c for r, c in row3]
    assert all(r == 2 for r, _ in row3), "row 3 can only hold tiles of the original row 3"
    height = rgb.shape[0]

    # Rows between row 2 and row 3: swap the old row 3's upper shadow for the new one's.
    gap = slice(GAP_TOP, ROW_TOP[2])
    above_row1 = rgb[GAP_TOP - TOP_SHADOW_SHIFT:ROW_TOP[2] - TOP_SHADOW_SHIFT]     # 3 tiles' upper shadow, clean
    new[gap] = np.clip(rgb[gap] - above_row1 + compose_row(above_row1, keep), 0, BG)

    # Row 3 and everything below it: the composed row, plus the last traces of row 2's lower shadow where it is
    # no longer covered by a card (2 grey levels at most).
    below = slice(ROW_TOP[2], height)
    composed = compose_row(rgb[below], keep)
    below_row3 = np.full_like(composed, BG)                    # the same lower shadow, seen clean below row 3
    below_row3[:height - ROW_TOP[2] - ROW_STEP] = rgb[ROW_TOP[2] + ROW_STEP:]
    shadow = np.clip((BG - composed) - (BG - compose_row(below_row3, keep)) + (BG - below_row3), 0, BG)
    in_card = np.zeros(composed.shape[:2], dtype=bool)
    for x in card_columns(len(keep)):
        in_card[:CARD_H + 1, x:x + W] = True                   # + the anti-aliased bottom row
    new[below] = np.where(in_card[..., None], composed, BG - shadow)
    return new


def build(row2, row3):
    """Return the re-flowed banner as a PIL image (alpha channel of the original kept)."""
    original = np.array(Image.open(ORIGINAL).convert("RGBA")).astype(int)
    out = np.dstack([reflow(original[..., :3], row2, row3), original[..., 3]])
    return Image.fromarray(out.astype(np.uint8), "RGBA")


VARIANTS = {
    "List_of_perks_2x_no_deck.png": ("Deck removed (8 perks)", [PODCASTS, BONUS, WRAP_UP], [EARLY_ACCESS, TSHIRT]),
    "List_of_perks_2x_no_deck_no_tshirt.png": ("Deck and T-shirt removed (7 perks)",
                                               [PODCASTS, BONUS, WRAP_UP], [EARLY_ACCESS]),
}


def _data_uri(image):
    buf = io.BytesIO()
    image.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    figures = [("Original", Image.open(ORIGINAL), None)]
    for name, (label, row2, row3) in VARIANTS.items():
        image = build(row2, row3)
        path = DOWNLOADS / name
        image.save(path, "PNG", optimize=True)
        figures.append((label, image, path))
        print(f"wrote {path}")
    cells = "".join(
        f"<figure><img src='{_data_uri(img)}' alt='{label}'><figcaption><b>{label}</b>"
        + (f"<br><span>{path}</span>" if path else "") + "</figcaption></figure>"
        for label, img, path in figures)
    PREVIEW.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,"
        "initial-scale=1'><title>CT+ perks banner without the deck</title><style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;margin:32px;"
        "color:#222;background:#e9e9e9}h1{font-size:26px;margin:0 0 4px}p{color:#666;margin:0 0 24px;font-size:15px}"
        ".row{display:flex;gap:28px;flex-wrap:wrap;align-items:flex-start}figure{margin:0;width:400px}"
        "img{width:100%;display:block}figcaption{font-size:14px;margin-top:10px;line-height:1.4}"
        "figcaption span{color:#666;font-size:12px;word-break:break-all}</style></head><body>"
        "<h1>Clearer Thinking Plus perks banner without the Life-Changing Questions deck</h1>"
        f"<p>{timestamp()} · tiles moved pixel for pixel from the original, same size (1091 × 1602)</p>"
        f"<div class='row'>{cells}</div></body></html>", encoding="utf-8")
    print(f"wrote {PREVIEW}")


if __name__ == "__main__":
    main()
