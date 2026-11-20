"""Instagram carousel (4:5, 1080 x 1350) of the key takeaways from the CT post
"What to Think About When You're Thinking About a Job Change"
(https://www.clearerthinking.org/post/what-to-think-about-when-youre-thinking-about-a-job-change).

The six takeaways are Igor's copy, VERBATIM (2026-11-20): never edit their wording here. Each one is split
at its first sentence into a headline and a body, nothing else changes. The emoji that opened each takeaway
are drawn as flat SVG icons (house style: no emoji). The cover and closing slide wording is ours: edit freely.

Run:  .venv/bin/python reports/job_change_carousel_2026-11-20_src/build.py
Out:  ~/Downloads/ct_job_change_carousel_2026-11-20/slide_01.png ... slide_08.png
      reports/job_change_carousel_2026-11-20.html  (overview of all slides, open in Chrome)
"""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".claude/skills/ct-infographic/scripts"))
import ct_infographic as kit  # noqa: E402

DATE = "2026-11-20"
OUT_DIR = Path.home() / "Downloads" / f"ct_job_change_carousel_{DATE}"
OVERVIEW = ROOT / "reports" / f"job_change_carousel_{DATE}.html"

# ---- wording: cover and closing slide (ours) -------------------------------------------------
ARTICLE_TITLE_1 = "What to Think About When You’re"
ARTICLE_TITLE_2 = "Thinking About a Job Change"
COVER_LABEL = "6 Key Takeaways"
SWIPE = "Swipe"
END_LINE_1 = "Read the full article"
END_LINE_2 = "on ClearerThinking.org"
END_NOTE = "Save this post for your next career decision."

# ---- wording: the takeaways (Igor's, verbatim) ------------------------------------------------
# (icon, headline, body paragraphs, optional list placed after the first body paragraph)
TAKEAWAYS = [
    ("compass", "Decide what you want to improve by changing your job.",
     ["Three things you might want to improve include:",
      "Those are different goals, and the same career move may affect them differently."],
     ["Job satisfaction", "Moment-to-moment happiness", "Overall life satisfaction"]),
    ("puzzle", "Interestingness is a weak guide to job satisfaction.",
     ["Career quizzes tend to focus on finding jobs that fit your interests, but it's important to consider "
      "other (stronger) predictors of satisfaction such as autonomy, connection with colleagues, and whether "
      "the work feels meaningful."], None),
    ("search", "Diagnose your dissatisfaction before deciding to leave.",
     ["Some feelings are likely to follow you from job to job, but others won't. Consider whether reshaping "
      "your current role could help."], None),
    ("coins", "A bigger salary does not guarantee a happier working life.",
     ["Higher income is more strongly associated with life satisfaction than with job satisfaction or "
      "moment-to-moment happiness, so weigh a raise against your other priorities."], None),
    ("flask", "Learn what a job feels like before committing to it.",
     ["Imagination is often a bad guide, and it is subject to biases. It can be better to ask people doing "
      "the work about their typical day, and test potential career changes through small projects, courses, "
      "volunteering, or temporary roles."], None),
    ("sun", "A fading honeymoon period does not mean a job change was a mistake.",
     ["Even if you do change job and experience a boost in happiness/satisfaction, that boost is likely to "
      "fade with time. That being said, temporary improvements can still make a move worthwhile."], None),
]

# ---- look ------------------------------------------------------------------------------------
FMT = kit.FORMATS["portrait"]          # 1600 x 2000 canvas
SCALE = 1080 / FMT["width"]            # export straight to Instagram's 1080 x 1350
MARGIN = 140
HEAD_PX, BODY_PX = 84, 50

S = 'fill="none" stroke="{c}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"'
INK, BLUE, ORANGE = kit.INK, kit.BLUE_RAMP[3], kit.ORANGE

# Flat icons on a 100 x 100 grid: blue line work, one orange detail each.
ICONS = {
    "compass": f'<circle cx="50" cy="50" r="34" {S.format(c=BLUE)}/>'
               f'<path d="M50 24 L58 50 L50 76 L42 50 Z" fill="{BLUE}"/>'
               f'<path d="M50 24 L58 50 L42 50 Z" fill="{ORANGE}"/><circle cx="50" cy="50" r="3.5" fill="#fff"/>',
    "puzzle": f'<path d="M22 34 H40 a8 8 0 1 1 16 0 H74 V52 a8 8 0 1 0 0 16 V80 H22 V68 a8 8 0 1 1 0 -16 Z" '
              f'{S.format(c=BLUE)}/><path d="M48 52 a8 8 0 1 1 0 16" {S.format(c=ORANGE)}/>',
    "search": f'<circle cx="44" cy="44" r="22" {S.format(c=BLUE)}/>'
              f'<path d="M60 60 L78 78" {S.format(c=BLUE)} stroke-width="7"/>'
              f'<path d="M34 44 a10 10 0 0 1 10 -10" {S.format(c=ORANGE)}/>',
    "coins": f'<ellipse cx="44" cy="70" rx="24" ry="8" {S.format(c=BLUE)}/>'
             f'<path d="M20 70 V58 M68 70 V58" {S.format(c=BLUE)}/><ellipse cx="44" cy="58" rx="24" ry="8" {S.format(c=BLUE)}/>'
             f'<path d="M20 58 V46 M68 58 V46" {S.format(c=BLUE)}/><ellipse cx="44" cy="46" rx="24" ry="8" {S.format(c=BLUE)}/>'
             f'<circle cx="74" cy="30" r="12" {S.format(c=ORANGE)}/>',
    "flask": f'<path d="M40 20 H60 M43 20 V42 L24 76 a4 4 0 0 0 4 6 H72 a4 4 0 0 0 4 -6 L57 42 V20" {S.format(c=BLUE)}/>'
             f'<path d="M33 62 H67 L74 76 a2 2 0 0 1 -2 3 H28 a2 2 0 0 1 -2 -3 Z" fill="{ORANGE}"/>',
    "sun": f'<circle cx="40" cy="40" r="13" {S.format(c=ORANGE)}/>'
           + "".join(f'<path d="M{40 + 20 * dx:.1f} {40 + 20 * dy:.1f} L{40 + 27 * dx:.1f} {40 + 27 * dy:.1f}" {S.format(c=ORANGE)}/>'
                     for dx, dy in [(0, -1), (-1, 0), (-0.707, -0.707), (0.707, -0.707), (-0.707, 0.707)])
           + f'<path d="M36 78 a12 12 0 0 1 4 -23 a16 16 0 0 1 30 4 a10 10 0 0 1 2 19 Z" fill="#fff" {S.format(c=BLUE)}/>',
}


def icon(name: str, size: int) -> str:
    return (f'<div class="badge" style="width:{size}px;height:{size}px">'
            f'<svg viewBox="0 0 100 100" width="{size * 0.62:.0f}" height="{size * 0.62:.0f}">{ICONS[name]}</svg></div>')


def dots(current: int, total: int) -> str:
    return '<div class="dots">' + "".join(
        f'<span class="{"on" if i == current else ""}"></span>' for i in range(total)) + "</div>"


CSS = f"""
#canvas {{ position:relative; }}
.main {{ flex:1; display:flex; flex-direction:column; justify-content:center; padding:0 {MARGIN}px; }}
.badge {{ border-radius:50%; background:{kit.BLUE_RAMP[0]}; display:flex; align-items:center; justify-content:center; flex:none; }}
.label {{ font-size:28px; font-weight:600; text-transform:uppercase; letter-spacing:3.4px; opacity:.7; }}
.head {{ font-size:{HEAD_PX}px; font-weight:600; line-height:1.18; letter-spacing:-0.3px; text-wrap:balance; margin:0; }}
.rule {{ width:120px; height:6px; border-radius:3px; background:{ORANGE}; margin:56px 0 52px; }}
.body p {{ font-size:{BODY_PX}px; font-weight:400; line-height:1.5; margin:0 0 34px; text-wrap:pretty; }}
.list {{ display:flex; flex-direction:column; gap:16px; margin:6px 0 40px; }}
.list div {{ background:{kit.BLUE_RAMP[0]}; border-radius:12px; padding:24px 34px; font-size:{BODY_PX}px; font-weight:600; }}
.top {{ display:flex; align-items:center; gap:40px; margin-bottom:64px; }}
.dots {{ display:flex; gap:16px; justify-content:center; padding:0 0 56px; }}
.dots span {{ width:16px; height:16px; border-radius:50%; background:{kit.BLUE_RAMP[1]}; }}
.dots span.on {{ background:{ORANGE}; width:48px; border-radius:8px; }}
.cover {{ align-items:center; text-align:center; }}
.cover .t {{ font-size:112px; font-weight:600; line-height:1.14; letter-spacing:-0.5px; text-wrap:balance; }}
.cover .t .l2 {{ color:{kit.BLUE}; }}
.cover .label {{ margin-bottom:64px; }}
.row {{ display:flex; gap:28px; justify-content:center; margin-top:110px; }}
.swipe {{ margin-top:110px; font-size:34px; font-weight:600; color:{kit.BLUE}; display:flex; align-items:center; gap:18px; }}
.end .t {{ font-size:104px; }}
.end .note {{ margin-top:80px; font-size:{BODY_PX}px; line-height:1.45; opacity:.8; }}
.end .src {{ margin-top:72px; font-size:40px; font-style:italic; font-weight:500; opacity:.75; text-wrap:balance; }}
"""

ARROW = (f'<svg width="64" height="24" viewBox="0 0 64 24"><path d="M2 12 H58 M46 2 L60 12 L46 22" '
         f'{S.format(c=kit.BLUE)}/></svg>')


def cover_body(total: int) -> str:
    return (f'<div class="main cover"><div class="label">{COVER_LABEL}</div>'
            f'<div class="t"><div>{ARTICLE_TITLE_1}</div><div class="l2">{ARTICLE_TITLE_2}</div></div>'
            f'<div class="row">{"".join(icon(t[0], 132) for t in TAKEAWAYS)}</div>'
            f'<div class="swipe">{SWIPE} {ARROW}</div></div>{dots(0, total)}')


def takeaway_body(i: int, total: int) -> str:
    name, head, paras, items = TAKEAWAYS[i]
    parts = [f"<p>{paras[0]}</p>"]
    if items:
        parts.append('<div class="list">' + "".join(f"<div>{x}</div>" for x in items) + "</div>")
    parts += [f"<p>{p}</p>" for p in paras[1:]]
    return (f'<div class="main"><div class="top">{icon(name, 190)}'
            f'<div class="label">Key takeaway {i + 1} of {len(TAKEAWAYS)}</div></div>'
            f'<h1 class="head">{head}</h1><div class="rule"></div>'
            f'<div class="body">{"".join(parts)}</div></div>{dots(i + 1, total)}')


def end_body(total: int) -> str:
    return (f'<div class="main cover end"><div class="t"><div>{END_LINE_1}</div><div class="l2">{END_LINE_2}</div></div>'
            f'<div class="src">“{ARTICLE_TITLE_1} {ARTICLE_TITLE_2}”</div>'
            f'<div class="note">{END_NOTE}</div></div>{dots(total - 1, total)}')


def slides() -> list[tuple[str, str]]:
    """(alt text, body html) for every slide, in order."""
    total = len(TAKEAWAYS) + 2
    out = [(f"Cover: {ARTICLE_TITLE_1} {ARTICLE_TITLE_2}", cover_body(total))]
    out += [(TAKEAWAYS[i][1], takeaway_body(i, total)) for i in range(len(TAKEAWAYS))]
    out.append((f"{END_LINE_1} {END_LINE_2}", end_body(total)))
    return out


def overview(paths: list[Path]) -> str:
    imgs = "".join(f'<img src="{p.as_uri()}" alt="slide {n}">' for n, p in enumerate(paths, 1))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Job Change Carousel</title>
<style>body {{ margin:0; padding:32px; background:#eee; font-family:{kit.FONT_STACK}; color:{INK}; }}
h1 {{ font-size:24px; font-weight:600; margin:0 0 4px; }} .sub {{ color:#666; margin:0 0 24px; font-size:15px; }}
.strip {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(320px, 1fr)); gap:20px; }}
img {{ width:100%; border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,.12); background:#fff; }}</style></head>
<body><h1>Instagram carousel: job change key takeaways</h1>
<p class="sub">{kit.timestamp()} · {len(paths)} slides, 1080 x 1350 · PNGs in {OUT_DIR}</p>
<div class="strip">{imgs}</div></body></html>"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    paths = []
    for n, (alt, body) in enumerate(slides(), 1):
        png = OUT_DIR / f"slide_{n:02d}.png"
        html = kit.page_html(body_html=body, css=CSS, width=FMT["width"], height=FMT["height"],
                             name=f"Job change carousel, slide {n}", alt=alt, png_path=png)
        kit.export(html, tmp / f"slide_{n:02d}.html", png, width=FMT["width"], height=FMT["height"], scale=SCALE)
        paths.append(png)
    OVERVIEW.write_text(overview(paths), encoding="utf-8")
    print("\n".join(str(p) for p in paths + [OVERVIEW]))


if __name__ == "__main__":
    main()
