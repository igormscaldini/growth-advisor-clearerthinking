"""Builds the "7 levels" staircase infographic in the Clearer Thinking flat style.

Content (level names and descriptions) is copied from the original staircase image Igor shared on
2026-11-06; the look follows the "5 Layers of Perception" graphic (white background, blue ramp,
grey footer with the logo). Everything editable lives in the constants below.

Run:  .venv/bin/python reports/integrative_complexity_staircase_2026-11-06_src/build.py [--format square|landscape]
Out:  reports/integrative_complexity_staircase[_square]_2026-11-06.html  (preview, open in Chrome)
      ~/Downloads/ct_integrative_complexity_staircase[_square]_2026-11-06.png  (the deliverable)
"""
import argparse
from datetime import datetime
from pathlib import Path
import re

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
LOGO_SVG = ROOT / "Branding assets/04 Logo/04 Logo/Clearer Thinking Logo/01 MAIN LOGO (on WHITE bg)/Logo-03.svg"

# ---- wording -------------------------------------------------------------------------------
# The title is NOT in the original image (it had none): edit freely.
TITLE_LINE_1 = "From One Angle to the Bigger Picture:"
TITLE_LINE_2 = "The 7 Levels of Integrative Complexity"

# (heading, description). Even levels are the in-between "hints at" stages.
LEVELS = [
    ("One Angle", "Only one way to see things considered"),
    ("Hints at", "more than one angle"),
    ("Several Angles", "Each treated as legitimate"),
    ("Hints at", "a connection between angles"),
    ("Angles Connected", "Explains how they shape each other"),
    ("Hints at", "a bigger picture"),
    ("A Bigger Picture", "Explains how it all fits together"),
]

# (first column, last column, heading, description), columns counted from 1.
GROUPS = [
    (2, 3, "Differentiation", "Seeing more than one angle"),
    (4, 7, "Differentiation + Integration", "Seeing more than one angle, and connecting them"),
]

# ---- look ----------------------------------------------------------------------------------
BLUE = "#3b84f7"       # title blue, sampled from the reference graphic
ANGLE_A = "#3b83f1"    # first angle (blue dot)
ANGLE_B = "#ee8031"    # second angle (orange dot); pair validated for colour-blind separation
LINK = "#233b47"       # connections and the "bigger picture" ring (brand dark accent)
INK = "#303030"        # brand main dark
SOLID_FILL = {1: "#dcebfc", 3: "#b0d2f8", 5: "#7cb4f5", 7: "#2a6fe0"}   # full stages, light to dark
GHOST = {2: ("#f3f8fe", "#8dbbf4"), 4: ("#eaf3fd", "#5c9df2"), 6: ("#e1edfc", "#2a6fe0")}  # (fill, dashed edge)

# Stroke widths (px). Kept thin on purpose (Igor, 2026-11-06: lighter lines and fonts).
LINE = 2          # brackets and dashed step outlines
GLYPH_LINE = 2.4  # arrows and rings in the dot icons
GLYPH_W, GLYPH_H = 200, 150

# Canvas size, stair geometry and type sizes, all in px. h=None means "as tall as the content".
# `scale` is the export multiplier: square exports at 2160 x 2160 (2 x the 1080 social standard).
LAYOUTS = {
    "landscape": dict(suffix="", w=1600, h=None, scale=2, margin_x=60, gap=14, base_h=226, step_h=48,
                      title=58, title_pad=62, step_pad=22, lvl=16, head=27, desc=22, ghead=24, gdesc=22,
                      groups_pad=44, footer_h=112, logo_h=64),
    "square": dict(suffix="_square", w=1600, h=1600, scale=1.35, margin_x=44, gap=10, base_h=318, step_h=84,
                   title=64, title_pad=74, step_pad=28, lvl=18, head=31, desc=27, ghead=27, gdesc=26,
                   groups_pad=50, footer_h=136, logo_h=76),
}


def glyph(level: int) -> str:
    """The dots above a step: one angle, two angles, linked angles, then both inside a ring."""
    cx, cy = GLYPH_W / 2, GLYPH_H / 2
    ax, bx, r = cx - 31, cx + 31, 20
    dotted = f'stroke-width="{GLYPH_LINE}" stroke-dasharray="2 8" stroke-linecap="round"'
    parts = []
    if level == 7:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="68" fill="#eef5fe" stroke="{LINK}" stroke-width="{GLYPH_LINE}"/>')
    if level == 6:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="68" fill="none" stroke="{LINK}" {dotted}/>')
    if level >= 4:
        top = f"M {ax + 9},{cy - 27} Q {cx},{cy - 50} {bx - 11},{cy - 29}"
        bottom = f"M {bx - 9},{cy + 27} Q {cx},{cy + 50} {ax + 11},{cy + 29}"
        if level == 4:
            style = f'stroke="{LINK}" {dotted}'
        else:
            style = f'stroke="{LINK}" stroke-width="{GLYPH_LINE}" marker-end="url(#arrowhead)"'
        parts += [f'<path d="{d}" fill="none" {style}/>' for d in (top, bottom)]
    if level == 1:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{ANGLE_A}"/>')
    else:
        parts.append(f'<circle cx="{ax}" cy="{cy}" r="{r}" fill="{ANGLE_A}"/>')
        if level == 2:
            parts.append(f'<circle cx="{bx}" cy="{cy}" r="{r - 1.2}" fill="none" stroke="{ANGLE_B}" {dotted}/>')
        else:
            parts.append(f'<circle cx="{bx}" cy="{cy}" r="{r}" fill="{ANGLE_B}"/>')
    if level == 7:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="6" fill="{LINK}"/>')
    return (f'<svg class="glyph" viewBox="0 0 {GLYPH_W} {GLYPH_H}" width="{GLYPH_W}" height="{GLYPH_H}" '
            f'aria-hidden="true">{"".join(parts)}</svg>')


def step(level: int, heading: str, text: str, lay: dict) -> str:
    height = lay["base_h"] + lay["step_h"] * (level - 1)
    if level in SOLID_FILL:
        css = f"background:{SOLID_FILL[level]};"
    else:
        fill, edge = GHOST[level]
        css = f"background:{fill}; border:{LINE}px dashed {edge};"
    kind = "final" if level == 7 else ("hint" if level in GHOST else "full")
    return (f'<div class="col">{glyph(level)}'
            f'<div class="step {kind}" style="height:{height}px; {css}">'
            f'<div class="lvl">Level {level}</div><div class="head">{heading}</div>'
            f'<div class="desc">{text}</div></div></div>')


def group(first: int, last: int, heading: str, text: str) -> str:
    return (f'<div class="group" style="grid-column:{first} / {last + 1}"><div class="bracket"></div>'
            f'<div class="ghead">{heading}</div><div class="gdesc">{text}</div></div>')


def logo_markup() -> str:
    svg = LOGO_SVG.read_text(encoding="utf-8")
    svg = svg[svg.index("<svg"):]                      # drop the XML declaration and comment
    return re.sub(r"<svg ", '<svg class="logo" ', svg, count=1)


def out_paths(lay: dict) -> tuple[Path, Path]:
    name = f"integrative_complexity_staircase{lay['suffix']}_2026-11-06"
    return ROOT / f"reports/{name}.html", Path.home() / f"Downloads/ct_{name}.png"


def build_html(lay: dict, stamp: str) -> str:
    steps = "".join(step(i + 1, h, t, lay) for i, (h, t) in enumerate(LEVELS))
    groups = "".join(group(*g) for g in GROUPS)
    fixed_height = f"height:{lay['h']}px; display:flex; flex-direction:column;" if lay["h"] else ""
    png_out = out_paths(lay)[1]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>7 Levels Staircase</title>
<style>
  html, body {{ margin:0; background:#e9e9e9; }}
  body {{ font-family:"Avenir Next", Avenir, "Montserrat", "Helvetica Neue", Arial, sans-serif; color:{INK}; }}
  .meta {{ padding:14px 24px 12px; font-size:15px; color:#555; }}
  .meta b {{ color:{INK}; font-size:17px; font-weight:600; }}
  #canvas {{ width:{lay['w']}px; background:#fff; {fixed_height} }}
  .title {{ text-align:center; padding:{lay['title_pad']}px 40px 0; font-weight:600; font-size:{lay['title']}px;
            line-height:1.22; letter-spacing:-0.2px; }}
  .title .l2 {{ color:{BLUE}; }}
  .stairs, .groups {{ display:grid; grid-template-columns:repeat(7, 1fr); column-gap:{lay['gap']}px;
                      margin:0 {lay['margin_x']}px; }}
  .stairs {{ align-items:end; margin-top:auto; padding-top:6px; }}
  .col {{ display:flex; flex-direction:column; align-items:center; }}
  .glyph {{ display:block; margin-bottom:6px; }}
  .step {{ box-sizing:border-box; width:100%; border-radius:12px; padding:{lay['step_pad']}px 8px 0; text-align:center; }}
  .lvl {{ font-size:{lay['lvl']}px; font-weight:600; letter-spacing:2.4px; text-transform:uppercase; opacity:.7; }}
  .head {{ font-size:{lay['head']}px; font-weight:600; line-height:1.14; margin-top:10px; text-wrap:balance; }}
  .desc {{ font-size:{lay['desc']}px; font-weight:400; line-height:1.27; margin-top:10px; text-wrap:balance; }}
  .step.hint .head {{ font-style:italic; font-weight:500; }}
  .step.hint .desc {{ margin-top:3px; }}
  .step.final {{ color:#fff; }}
  .step.final .lvl {{ opacity:.9; }}
  .groups {{ margin-top:16px; padding-bottom:{lay['groups_pad']}px; }}
  .group {{ text-align:center; }}
  .bracket {{ height:13px; border:{LINE}px solid {BLUE}; border-top:0; border-radius:0 0 9px 9px; margin:0 3px 14px; }}
  .ghead {{ font-size:{lay['ghead']}px; font-weight:600; letter-spacing:1.6px; text-transform:uppercase; }}
  .gdesc {{ font-size:{lay['gdesc']}px; font-weight:400; margin-top:4px; }}
  .footer {{ background:#f5f5f5; height:{lay['footer_h']}px; flex:none; display:flex; align-items:center;
             justify-content:center; }}
  .logo {{ height:{lay['logo_h']}px; width:auto; display:block; }}
</style></head>
<body>
<div class="meta"><b>7 levels staircase, Clearer Thinking style</b> &nbsp;·&nbsp; built {stamp} &nbsp;·&nbsp;
  PNG saved to {png_out} &nbsp;·&nbsp; this grey bar is not part of the image</div>
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
  <marker id="arrowhead" viewBox="0 0 10 10" refX="7.5" refY="5" markerWidth="5.4" markerHeight="5.4" orient="auto">
    <path d="M0.5,0.8 L9.5,5 L0.5,9.2 z" fill="{LINK}"/></marker></defs></svg>
<div id="canvas" role="img" aria-label="Staircase of seven levels of thinking, from one angle to a bigger picture">
  <div class="title"><div>{TITLE_LINE_1}</div><div class="l2">{TITLE_LINE_2}</div></div>
  <div class="stairs">{steps}</div>
  <div class="groups">{groups}</div>
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


def render_png(lay: dict) -> None:
    html_out, png_out = out_paths(lay)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        # Tall viewport so the preview-fit script leaves the canvas at full size.
        page = browser.new_page(viewport={"width": lay["w"], "height": 2400}, device_scale_factor=lay["scale"])
        page.goto(html_out.as_uri())
        page.evaluate("document.fonts.ready")
        page.locator("#canvas").screenshot(path=str(png_out))
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=sorted(LAYOUTS), default="square")
    lay = LAYOUTS[parser.parse_args().format]
    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d ") + now.strftime("%I:%M%p").lstrip("0").lower()
    html_out, png_out = out_paths(lay)
    html_out.write_text(build_html(lay, stamp), encoding="utf-8")
    render_png(lay)
    print(f"HTML: {html_out}\nPNG:  {png_out}")
