"""Builds the "7 levels" staircase infographic in the Clearer Thinking flat style.

Content (level names and descriptions) is copied from the original staircase image Igor shared on
2026-11-06; the look follows the "5 Layers of Perception" graphic (white background, blue ramp,
grey footer with the logo). Everything editable lives in the constants below.

Run:  .venv/bin/python reports/integrative_complexity_staircase_2026-11-06_src/build.py
Out:  reports/integrative_complexity_staircase_2026-11-06.html  (preview, opened in Chrome)
      ~/Downloads/ct_integrative_complexity_staircase_2026-11-06.png  (the deliverable, 3200 px wide)
"""
from datetime import datetime
from pathlib import Path
import re

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
LOGO_SVG = ROOT / "Branding assets/04 Logo/04 Logo/Clearer Thinking Logo/01 MAIN LOGO (on WHITE bg)/Logo-03.svg"
HTML_OUT = ROOT / "reports/integrative_complexity_staircase_2026-11-06.html"
PNG_OUT = Path.home() / "Downloads/ct_integrative_complexity_staircase_2026-11-06.png"

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

CANVAS_W = 1600
BASE_H, STEP_H = 226, 48          # height of level 1 and the rise per level, px
GLYPH_W, GLYPH_H = 200, 150


def glyph(level: int) -> str:
    """The dots above a step: one angle, two angles, linked angles, then both inside a ring."""
    cx, cy = GLYPH_W / 2, GLYPH_H / 2
    ax, bx, r = cx - 31, cx + 31, 20
    parts = []
    if level == 7:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="68" fill="#eef5fe" stroke="{LINK}" stroke-width="4"/>')
    if level == 6:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="68" fill="none" stroke="{LINK}" stroke-width="3" '
                     f'stroke-dasharray="3 9" stroke-linecap="round"/>')
    if level >= 4:
        top = f"M {ax + 9},{cy - 27} Q {cx},{cy - 50} {bx - 11},{cy - 29}"
        bottom = f"M {bx - 9},{cy + 27} Q {cx},{cy + 50} {ax + 11},{cy + 29}"
        if level == 4:
            style = f'stroke="{LINK}" stroke-width="3" stroke-dasharray="3 9" stroke-linecap="round"'
        else:
            style = f'stroke="{LINK}" stroke-width="3.5" marker-end="url(#arrowhead)"'
        parts += [f'<path d="{d}" fill="none" {style}/>' for d in (top, bottom)]
    if level == 1:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{ANGLE_A}"/>')
    else:
        parts.append(f'<circle cx="{ax}" cy="{cy}" r="{r}" fill="{ANGLE_A}"/>')
        if level == 2:
            parts.append(f'<circle cx="{bx}" cy="{cy}" r="{r - 1.5}" fill="none" stroke="{ANGLE_B}" '
                         f'stroke-width="3" stroke-dasharray="3 8" stroke-linecap="round"/>')
        else:
            parts.append(f'<circle cx="{bx}" cy="{cy}" r="{r}" fill="{ANGLE_B}"/>')
    if level == 7:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="7" fill="{LINK}"/>')
    return (f'<svg class="glyph" viewBox="0 0 {GLYPH_W} {GLYPH_H}" width="{GLYPH_W}" height="{GLYPH_H}" '
            f'aria-hidden="true">{"".join(parts)}</svg>')


def step(level: int, heading: str, text: str) -> str:
    height = BASE_H + STEP_H * (level - 1)
    if level in SOLID_FILL:
        css = f"background:{SOLID_FILL[level]};"
    else:
        fill, edge = GHOST[level]
        css = f"background:{fill}; border:3px dashed {edge};"
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


def build_html(stamp: str) -> str:
    steps = "".join(step(i + 1, h, t) for i, (h, t) in enumerate(LEVELS))
    groups = "".join(group(*g) for g in GROUPS)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>7 Levels Staircase</title>
<style>
  html, body {{ margin:0; background:#e9e9e9; }}
  body {{ font-family:"Avenir Next", Avenir, "Montserrat", "Helvetica Neue", Arial, sans-serif; color:{INK}; }}
  .meta {{ padding:18px 24px 14px; font-size:15px; color:#555; }}
  .meta b {{ color:{INK}; font-size:17px; }}
  #canvas {{ width:{CANVAS_W}px; background:#fff; transform-origin:top left; }}
  .title {{ text-align:center; padding:62px 60px 0; font-weight:700; font-size:58px; line-height:1.22; letter-spacing:-0.3px; }}
  .title .l2 {{ color:{BLUE}; }}
  .stairs, .groups {{ display:grid; grid-template-columns:repeat(7, 1fr); column-gap:14px; margin:0 60px; }}
  .stairs {{ align-items:end; margin-top:6px; }}
  .col {{ display:flex; flex-direction:column; align-items:center; }}
  .glyph {{ display:block; margin-bottom:6px; }}
  .step {{ box-sizing:border-box; width:100%; border-radius:12px; padding:22px 10px 0; text-align:center; }}
  .lvl {{ font-size:16px; font-weight:700; letter-spacing:2.4px; text-transform:uppercase; opacity:.72; }}
  .head {{ font-size:27px; font-weight:700; line-height:1.14; margin-top:9px; text-wrap:balance; }}
  .desc {{ font-size:22px; font-weight:500; line-height:1.27; margin-top:9px; text-wrap:balance; }}
  .step.hint .head {{ font-style:italic; font-weight:600; }}
  .step.hint .desc {{ margin-top:2px; }}
  .step.final {{ color:#fff; }}
  .step.final .lvl {{ opacity:.9; }}
  .groups {{ margin-top:16px; padding-bottom:44px; }}
  .group {{ text-align:center; }}
  .bracket {{ height:13px; border:3px solid {BLUE}; border-top:0; border-radius:0 0 9px 9px; margin:0 3px 13px; }}
  .ghead {{ font-size:24px; font-weight:700; letter-spacing:1.6px; text-transform:uppercase; }}
  .gdesc {{ font-size:22px; font-weight:500; margin-top:4px; }}
  .footer {{ background:#f5f5f5; height:112px; display:flex; align-items:center; justify-content:center; }}
  .logo {{ height:64px; width:auto; display:block; }}
</style></head>
<body>
<div class="meta"><b>7 levels staircase, Clearer Thinking style</b> &nbsp;·&nbsp; built {stamp} &nbsp;·&nbsp;
  PNG saved to {PNG_OUT} &nbsp;·&nbsp; this grey bar is not part of the image</div>
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
  <marker id="arrowhead" viewBox="0 0 10 10" refX="7.5" refY="5" markerWidth="4.6" markerHeight="4.6" orient="auto">
    <path d="M0.5,0.8 L9.5,5 L0.5,9.2 z" fill="{LINK}"/></marker></defs></svg>
<div id="canvas" role="img" aria-label="Staircase of seven levels of thinking, from one angle to a bigger picture">
  <div class="title"><div>{TITLE_LINE_1}</div><div class="l2">{TITLE_LINE_2}</div></div>
  <div class="stairs">{steps}</div>
  <div class="groups">{groups}</div>
  <div class="footer">{logo_markup()}</div>
</div>
<script>
  // Preview only: shrink the fixed-width canvas to fit a narrower window.
  function fit() {{
    var c = document.getElementById('canvas'), s = Math.min(1, (window.innerWidth) / {CANVAS_W});
    c.style.transform = s < 1 ? 'scale(' + s + ')' : '';
  }}
  window.addEventListener('resize', fit); fit();
</script>
</body></html>"""


def render_png() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": CANVAS_W, "height": 1300}, device_scale_factor=2)
        page.goto(HTML_OUT.as_uri())
        page.evaluate("document.fonts.ready")
        page.locator("#canvas").screenshot(path=str(PNG_OUT))
        browser.close()


if __name__ == "__main__":
    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d ") + now.strftime("%I:%M%p").lstrip("0").lower()
    HTML_OUT.write_text(build_html(stamp), encoding="utf-8")
    render_png()
    print(f"HTML: {HTML_OUT}\nPNG:  {PNG_OUT}")
