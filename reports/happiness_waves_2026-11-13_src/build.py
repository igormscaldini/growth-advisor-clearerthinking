"""Builds "The waves of your happiness" in the Clearer Thinking flat style.

Content AND layout are copied from the graphic Igor shared on 2026-11-13 (title + subtitle top left, small
wave drawing top right, ten rows with the wave on the left and its common duration on a log-scale axis on
the right, "Find out more" link bottom right). Only the styling changes: CT palette, Avenir, flat rounded
shapes, logo footer (house style of the integrative-complexity staircase).

Marker positions were measured from the source pixels (its axis is 98 px per decade, starting at 0.1 s)
and are stored here in seconds, so every bar and dot sits where it sat in the original.

Run:  .venv/bin/python reports/happiness_waves_2026-11-13_src/build.py
Out:  reports/happiness_waves_2026-11-13.html (preview) and ~/Downloads/ct_happiness_waves_2026-11-13.png
"""
from __future__ import annotations

from math import exp, log10
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".claude/skills/ct-infographic/scripts"))
import ct_infographic as kit  # noqa: E402

# ---- wording (exactly as in the source) ------------------------------------------------------
TITLE = "The waves of your happiness"
SUBTITLE = "Multiple waves shape how you feel at the same time."
COL_LABEL = "Wave type"
AXIS_LABEL = "Common duration on a log scale"
LINK_LEAD, LINK_URL = "Find out more at", "ClearerThinking.org/happinesswaves"
ALT = "Ten waves that shape how you feel, from reactions lasting seconds to aging over decades, on a log time scale"

S, MIN, H, D, WK, YR = 1, 60, 3600, 86400, 604800, 31_557_600
# (name, duration, example, start in seconds, end in seconds or None for a dot)
WAVES = [
    ("Reactions", "0.1 sec to a few seconds", "Startling at a loud noise", 0.1, 2.9),
    ("Setting and attention", "About 1 minute", "Enjoying a walk or doing taxes", 1 * MIN, None),
    ("Body", "About 10 minutes", "Hunger, pain, or a warm bath", 10 * MIN, None),
    ("Mood", "A few hours", "Waking up in a funk", 3 * H, None),
    ("Circadian rhythm", "About 1 day", "Daily shifts in alertness", 1 * D, None),
    ("Acute illness or injury", "A few days to a few weeks", "Recovering from illness or injury", 3 * D, 20 * D),
    ("Loss and gain", "Weeks to years", "A breakup or a windfall", 2 * WK, 4.8 * YR),
    ("Satisfaction and health", "About 1 year", "Life goals and overall health", 1 * YR, None),
    ("Identity", "Years", "How you feel about who you are", 3.9 * YR, None),
    ("Aging", "Decades", "Changes in your body and mind", 34 * YR, None),
]
TICKS = [("0.1 s", 0.1), ("1 s", 1 * S), ("1 min", MIN), ("1 h", H), ("1 d", D), ("1 wk", WK),
         ("1 yr", YR), ("10 yr", 10 * YR)]
AXIS_MIN, AXIS_MAX = 0.1, 4.1e9   # the source's axis runs from 0.1 s to its arrow (~130 years)

# ---- look ------------------------------------------------------------------------------------
W = 1600
LABEL_W = 680            # left column (badge + text)
CHART_PAD_R = 46         # space after the arrow
ROW_H, ROW_GAP = 72, 8
MARK = kit.BLUE_RAMP[4]
GRID = kit.BLUE_RAMP[1]
ROW_FILLS = (kit.BLUE_TINTS[0], kit.BLUE_TINTS[2])   # alternating, like the source's banding


def axis_pos(seconds: float) -> float:
    """Position on the log axis as a fraction of the chart width (0 = 0.1 s, 1 = end of the arrow)."""
    return (log10(seconds) - log10(AXIS_MIN)) / (log10(AXIS_MAX) - log10(AXIS_MIN))


def pct(seconds: float) -> str:
    return f"{axis_pos(seconds) * 100:.3f}%"


def waves_svg(width: int = 430, height: int = 104) -> str:
    """Three overlapping smooth waves (two blue, one orange), as in the source's top-right drawing."""
    def curve(bumps, base):
        pts = []
        for i in range(0, width + 1, 4):
            y = base - sum(a * exp(-((i - c) / s) ** 2) for a, c, s in bumps)
            pts.append(f"{i},{y:.1f}")
        return pts
    light = curve([(70, 120, 70), (30, 370, 60)], height - 14)
    dark = curve([(8, 90, 60), (56, 320, 65)], height - 6)
    orange = curve([(34, 175, 34)], height - 4)
    area = " ".join(light + [f"{width},{height}", f"0,{height}"])
    area2 = " ".join(dark + [f"{width},{height}", f"0,{height}"])
    line = 'fill="none" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"'
    return (f'<svg class="waves" viewBox="0 0 {width} {height}" width="{width}" height="{height}" aria-hidden="true">'
            f'<polygon points="{area}" fill="{kit.BLUE_TINTS[2]}"/>'
            f'<polygon points="{area2}" fill="{kit.BLUE_RAMP[0]}" opacity=".7"/>'
            f'<polyline points="{" ".join(light)}" stroke="{kit.BLUE_RAMP[3]}" {line}/>'
            f'<polyline points="{" ".join(orange)}" stroke="{kit.ORANGE}" {line}/>'
            f'<polyline points="{" ".join(dark)}" stroke="{kit.BLUE_RAMP[4]}" {line}/></svg>')


def marker(start: float, end: float | None) -> str:
    if end is None:
        return f'<div class="dot" style="left:{pct(start)}"></div>'
    return (f'<div class="bar" style="left:{pct(start)}; '
            f'width:calc({pct(end)} - {pct(start)})"></div>')


def row(i: int, name: str, dur: str, ex: str, start: float, end: float | None) -> str:
    return (f'<div class="row" style="background:{ROW_FILLS[i % 2]}">'
            f'<div class="lab"><div class="num">{i + 1}</div><div>'
            f'<div class="name">{name}</div><div class="sub"><b>{dur}</b> · {ex}</div></div></div>'
            f'<div class="track">{marker(start, end)}</div></div>')


CSS = f"""
  .head {{ display:flex; justify-content:space-between; align-items:flex-end; padding:46px 60px 0; }}
  .t1 {{ font-size:58px; font-weight:600; line-height:1.15; letter-spacing:-0.2px; }}
  .t2 {{ font-size:30px; font-weight:500; color:{kit.BLUE}; margin-top:6px; }}
  .waves {{ display:block; margin-bottom:4px; }}
  .table {{ position:relative; margin:22px 60px 0; }}
  .cols {{ display:flex; align-items:flex-end; height:74px; }}
  .lbl {{ font-size:17px; font-weight:600; letter-spacing:2.4px; text-transform:uppercase; opacity:.7; }}
  .cols .lbl.left {{ width:{LABEL_W}px; padding-left:8px; padding-bottom:12px; }}
  .axis {{ position:relative; flex:1; height:100%; margin-right:{CHART_PAD_R}px; }}
  .axis .lbl {{ position:absolute; left:0; top:0; }}
  .tick {{ position:absolute; bottom:16px; transform:translateX(-50%); font-size:20px; font-weight:500;
           white-space:nowrap; }}
  .tick.first {{ transform:none; }}
  .axisline {{ position:absolute; left:0; right:-{CHART_PAD_R - 12}px; bottom:4px; height:2px; background:{kit.DARK_ACCENT}; }}
  .axisline::after {{ content:""; position:absolute; right:-2px; top:-6px; border:7px solid transparent;
                      border-left:12px solid {kit.DARK_ACCENT}; border-right:0; }}
  .rows {{ display:flex; flex-direction:column; gap:{ROW_GAP}px; margin-top:10px; }}
  .row {{ display:flex; height:{ROW_H}px; border-radius:12px; }}
  .lab {{ width:{LABEL_W}px; display:flex; align-items:center; gap:16px; padding-left:16px; box-sizing:border-box; }}
  .num {{ flex:none; width:38px; height:38px; border-radius:50%; background:#fff; display:flex; align-items:center;
          justify-content:center; font-size:19px; font-weight:600; }}
  .name {{ font-size:27px; font-weight:600; line-height:1.1; }}
  .sub {{ font-size:20px; font-weight:400; margin-top:4px; white-space:nowrap; }}
  .sub b {{ font-weight:600; }}
  .track {{ position:relative; flex:1; margin-right:{CHART_PAD_R}px; z-index:2; }}
  .dot {{ position:absolute; top:50%; width:26px; height:26px; margin:-13px 0 0 -13px; border-radius:50%; background:{MARK}; }}
  .bar {{ position:absolute; top:50%; height:18px; margin-top:-9px; border-radius:9px; background:{MARK}; }}
  .grid {{ position:absolute; top:74px; bottom:0; left:{LABEL_W}px; right:{CHART_PAD_R}px; z-index:1; pointer-events:none; }}
  .grid i {{ position:absolute; top:0; bottom:0; border-left:2px dashed {GRID}; }}
  .more {{ text-align:right; font-size:22px; padding:22px 60px 26px; }}
  .more b {{ font-weight:600; }}
"""


def build_html(stamp: str = "", png_path: Path | str = "") -> str:
    ticks = "".join(f'<div class="tick{" first" if i == 0 else ""}" style="left:{pct(s)}">{t}</div>'
                    for i, (t, s) in enumerate(TICKS))
    grid = "".join(f'<i style="left:{pct(s)}"></i>' for _, s in TICKS)
    body = (f'<div class="head"><div><div class="t1">{TITLE}</div><div class="t2">{SUBTITLE}</div></div>'
            f'{waves_svg()}</div>'
            f'<div class="table"><div class="cols"><div class="lbl left">{COL_LABEL}</div>'
            f'<div class="axis"><div class="lbl">{AXIS_LABEL}</div>{ticks}<div class="axisline"></div></div></div>'
            f'<div class="grid">{grid}</div>'
            f'<div class="rows">{"".join(row(i, *w) for i, w in enumerate(WAVES))}</div></div>'
            f'<div class="more">{LINK_LEAD} <b>{LINK_URL}</b></div>')
    return kit.page_html(body_html=body, css=CSS, width=W, name="Happiness waves", alt=ALT,
                         png_path=png_path, stamp=stamp)


def main() -> None:
    html_out = ROOT / "reports/happiness_waves_2026-11-13.html"
    png_out = Path.home() / "Downloads/ct_happiness_waves_2026-11-13.png"
    kit.export(build_html(png_path=png_out), html_out, png_out, width=W, scale=1.35)
    print(png_out)


if __name__ == "__main__":
    main()
