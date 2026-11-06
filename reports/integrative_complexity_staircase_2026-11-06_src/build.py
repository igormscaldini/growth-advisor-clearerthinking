"""Builds the "7 levels" staircase infographic in the Clearer Thinking flat style.

Content (level names and descriptions) is copied from the original staircase image Igor shared on
2026-11-06; the look follows the "5 Layers of Perception" graphic. The shared style (palette, title,
logo footer, PNG export) comes from the ct-infographic skill's kit; this file holds the wording and
the staircase itself. It is the skill's worked example.

Run:  .venv/bin/python reports/integrative_complexity_staircase_2026-11-06_src/build.py [--format square|landscape]
Out:  reports/integrative_complexity_staircase[_square]_2026-11-06.html  (preview, open in Chrome)
      ~/Downloads/ct_integrative_complexity_staircase[_square]_2026-11-06.png  (the deliverable)
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".claude/skills/ct-infographic/scripts"))
import ct_infographic as kit  # noqa: E402

# ---- wording -------------------------------------------------------------------------------
# The title is NOT in the original image (it had none): edit freely.
TITLE_LINE_1 = "From One Angle to the Bigger Picture:"
TITLE_LINE_2 = "The 7 Levels of Integrative Complexity"
ALT = "Staircase of seven levels of thinking, from one angle to a bigger picture"

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
ANGLE_A = kit.BLUE_RAMP[3]   # first angle (blue dot)
ANGLE_B = kit.ORANGE         # second angle (orange dot); pair validated for colour-blind separation
LINK = kit.DARK_ACCENT       # connections and the "bigger picture" ring
SOLID_FILL = {1: kit.BLUE_RAMP[0], 3: kit.BLUE_RAMP[1], 5: kit.BLUE_RAMP[2], 7: kit.BLUE_RAMP[4]}  # full stages
GHOST = {2: (kit.BLUE_TINTS[0], "#8dbbf4"), 4: (kit.BLUE_TINTS[1], "#5c9df2"),
         6: (kit.BLUE_TINTS[2], kit.BLUE_RAMP[4])}   # in-between stages: (fill, dashed edge)

# Stroke widths (px). Kept thin on purpose (Igor, 2026-11-06: lighter lines and fonts).
LINE = 2          # brackets and dashed step outlines
GLYPH_LINE = 2.4  # arrows and rings in the dot icons
GLYPH_W, GLYPH_H = 200, 150

# Canvas preset plus stair geometry and type sizes, all in px.
LAYOUTS = {
    "landscape": dict(kit.FORMATS["landscape"], suffix="", margin_x=60, gap=14, base_h=226, step_h=48,
                      title=58, title_pad=62, step_pad=22, lvl=16, head=27, desc=22, ghead=24, gdesc=22,
                      groups_pad=44, footer_h=112, logo_h=64),
    "square": dict(kit.FORMATS["square"], suffix="_square", margin_x=44, gap=10, base_h=318, step_h=84,
                   title=64, title_pad=74, step_pad=28, lvl=18, head=31, desc=27, ghead=27, gdesc=26,
                   groups_pad=50, footer_h=136, logo_h=76),
}

ARROWHEAD = (f'<marker id="arrowhead" viewBox="0 0 10 10" refX="7.5" refY="5" markerWidth="5.4" '
             f'markerHeight="5.4" orient="auto"><path d="M0.5,0.8 L9.5,5 L0.5,9.2 z" fill="{LINK}"/></marker>')


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


def out_paths(lay: dict) -> tuple[Path, Path]:
    name = f"integrative_complexity_staircase{lay['suffix']}_2026-11-06"
    return ROOT / f"reports/{name}.html", Path.home() / f"Downloads/ct_{name}.png"


def staircase_css(lay: dict) -> str:
    return f"""
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
  .bracket {{ height:13px; border:{LINE}px solid {kit.BLUE}; border-top:0; border-radius:0 0 9px 9px; margin:0 3px 14px; }}
  .ghead {{ font-size:{lay['ghead']}px; font-weight:600; letter-spacing:1.6px; text-transform:uppercase; }}
  .gdesc {{ font-size:{lay['gdesc']}px; font-weight:400; margin-top:4px; }}"""


def build_html(lay: dict, stamp: str = "") -> str:
    steps = "".join(step(i + 1, h, t, lay) for i, (h, t) in enumerate(LEVELS))
    groups = "".join(group(*g) for g in GROUPS)
    return kit.page_html(
        body_html=f'<div class="stairs">{steps}</div><div class="groups">{groups}</div>',
        title_line_1=TITLE_LINE_1, title_line_2=TITLE_LINE_2, css=staircase_css(lay),
        width=lay["width"], height=lay["height"], title_size=lay["title"], title_pad=lay["title_pad"],
        footer_h=lay["footer_h"], logo_h=lay["logo_h"], name="7 levels staircase, Clearer Thinking style",
        alt=ALT, png_path=out_paths(lay)[1], stamp=stamp, svg_defs=ARROWHEAD)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=sorted(LAYOUTS), default="square")
    lay = LAYOUTS[parser.parse_args().format]
    html_out, png_out = out_paths(lay)
    kit.export(build_html(lay), html_out, png_out, width=lay["width"], height=lay["height"], scale=lay["scale"])
    print(f"HTML: {html_out}\nPNG:  {png_out}")
