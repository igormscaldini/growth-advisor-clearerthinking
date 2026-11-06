"""Clearer Thinking flat-infographic kit: palette, page shell (title + logo footer), PNG export, checks.

Used by the ct-infographic skill. Each graphic gets its own small build script that supplies the middle
of the page (HTML + CSS) and calls page_html() and export(). Worked example:
reports/integrative_complexity_staircase_2026-11-06_src/build.py
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

SKILL_DIR = Path(__file__).resolve().parents[1]
# Copy of "Branding assets/.../01 MAIN LOGO (on WHITE bg)/Logo-03.svg" (that folder is gitignored,
# so the skill carries its own copy and works from a fresh clone).
LOGO_SVG = SKILL_DIR / "assets/ct-logo-clearerthinking-org.svg"

# ---- palette (sampled from the "5 Layers of Perception" graphic + the Jan 2025 style guide) ----
BLUE = "#3b84f7"          # second title line, brackets, thin accents
INK = "#303030"           # all text on light fills (brand main dark)
ORANGE = "#ee8031"        # the single accent colour
DARK_ACCENT = "#233b47"   # connector lines, arrows, rings (brand dark accent)
FOOTER_GREY = "#f5f5f5"
# One hue, light to dark. Dark text reads on the first three; white text only on the last
# (white on BLUE_RAMP[3] is 3.7:1, too weak for body text).
BLUE_RAMP = ("#dcebfc", "#b0d2f8", "#7cb4f5", "#3b83f1", "#2a6fe0")
# Near-white fills for "ghost" shapes drawn with a dashed outline.
BLUE_TINTS = ("#f3f8fe", "#eaf3fd", "#e1edfc")

FONT_STACK = '"Avenir Next", Avenir, "Montserrat", "Helvetica Neue", Arial, sans-serif'

# Canvas presets. `scale` is the export multiplier, so the social formats land on exact multiples
# of the 1080 px standard. height=None means "as tall as the content".
FORMATS = {
    "landscape": dict(width=1600, height=None, scale=2),     # newsletter / blog, 3200 px wide
    "square": dict(width=1600, height=1600, scale=1.35),     # social 1:1, 2160 x 2160
    "portrait": dict(width=1600, height=2000, scale=1.35),   # social 4:5, 2160 x 2700
}


def timestamp(now: datetime | None = None) -> str:
    """'2026-11-06 8:05am' (Igor's report timestamp format)."""
    now = now or datetime.now()
    return now.strftime("%Y-%m-%d ") + now.strftime("%I:%M%p").lstrip("0").lower()


def logo_markup() -> str:
    """The ClearerThinking.org logo as inline SVG with class="logo"."""
    svg = LOGO_SVG.read_text(encoding="utf-8")
    svg = svg[svg.index("<svg"):]                      # drop the XML declaration and comment
    return re.sub(r"<svg ", '<svg class="logo" ', svg, count=1)


def _luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(colour_a: str, colour_b: str) -> float:
    """WCAG contrast ratio between two hex colours (1 to 21). Body text needs 4.5 or more."""
    hi, lo = sorted((_luminance(colour_a), _luminance(colour_b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def display_px(font_px: float, canvas_width: float, display_width: float) -> float:
    """Size a canvas font ends up at when the image is shown `display_width` px wide."""
    return font_px * display_width / canvas_width


def page_html(*, body_html: str, title_line_1: str = "", title_line_2: str = "", css: str = "",
              width: int = 1600, height: int | None = None, title_size: int = 58, title_pad: int = 62,
              footer_h: int = 112, logo_h: int = 64, name: str = "Clearer Thinking infographic",
              alt: str = "", png_path: Path | str = "", stamp: str = "", svg_defs: str = "") -> str:
    """Full preview page: a grey info bar (not exported) and the #canvas (title, body, logo footer).

    title_line_1 is dark and title_line_2 is blue; pass only one for a single-line title.
    With a fixed `height` the canvas is a flex column, so give the main block `margin-top:auto`
    (or flex:1) to place it. `css` is appended after the base rules; `svg_defs` holds shared
    <marker>/<symbol> definitions.
    """
    lines = "".join(f'<div class="{cls}">{text}</div>'
                    for cls, text in (("l1", title_line_1), ("l2", title_line_2)) if text)
    title = f'<div class="title">{lines}</div>' if lines else ""
    fixed_height = f"height:{height}px; display:flex; flex-direction:column;" if height else ""
    defs = (f'<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>{svg_defs}</defs></svg>'
            if svg_defs else "")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{name}</title>
<style>
  html, body {{ margin:0; background:#e9e9e9; }}
  body {{ font-family:{FONT_STACK}; color:{INK}; }}
  .meta {{ padding:14px 24px 12px; font-size:15px; color:#555; }}
  .meta b {{ color:{INK}; font-size:17px; font-weight:600; }}
  #canvas {{ width:{width}px; background:#fff; {fixed_height} }}
  .title {{ text-align:center; padding:{title_pad}px 40px 0; font-weight:600; font-size:{title_size}px;
            line-height:1.22; letter-spacing:-0.2px; }}
  .title .l2 {{ color:{BLUE}; }}
  .footer {{ background:{FOOTER_GREY}; height:{footer_h}px; flex:none; display:flex; align-items:center;
             justify-content:center; }}
  .logo {{ height:{logo_h}px; width:auto; display:block; }}
{css}
</style></head>
<body>
<div class="meta"><b>{name}</b> &nbsp;·&nbsp; built {stamp or timestamp()} &nbsp;·&nbsp;
  PNG saved to {png_path} &nbsp;·&nbsp; this grey bar is not part of the image</div>
{defs}
<div id="canvas" role="img" aria-label="{alt}">
  {title}
  {body_html}
  <div class="footer">{logo_markup()}</div>
</div>
<script>
  // Preview only: shrink the fixed-size canvas so it fits the window (the export viewport is big enough for 1:1).
  function fit() {{
    var c = document.getElementById('canvas'), bar = document.querySelector('.meta').offsetHeight;
    var s = Math.min(1, window.innerWidth / c.offsetWidth, (window.innerHeight - bar) / c.offsetHeight);
    c.style.zoom = s < 1 ? s : '';
  }}
  window.addEventListener('resize', fit); fit();
</script>
</body></html>"""


def export(html: str, html_path: Path, png_path: Path, *, width: int = 1600, height: int | None = None,
           scale: float = 2) -> None:
    """Write the preview page and screenshot its #canvas to a PNG (headless Chrome via Playwright)."""
    from playwright.sync_api import sync_playwright   # imported here so the pure helpers work without it

    html_path.write_text(html, encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        # Viewport taller than the canvas, so the preview-fit script leaves it at full size.
        page = browser.new_page(viewport={"width": width, "height": max(2400, (height or 0) + 400)},
                                device_scale_factor=scale)
        page.goto(html_path.as_uri())
        page.evaluate("document.fonts.ready")
        page.locator("#canvas").screenshot(path=str(png_path))
        browser.close()
