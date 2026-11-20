"""CT Instagram/LinkedIn carousel (4:5, 1080 x 1350): cover, one slide per key takeaway, closing slide with the owl.

This file is the single source of the carousel's LOOK (layout, type sizes, icons, owl, colours via the
ct-infographic kit). A carousel's WORDING lives in a JSON spec next to its output, so a new carousel never
copies or edits layout code. Approved look: the job-change carousel of 2026-11-20
(reports/job_change_carousel_2026-11-20_src/carousel.json).

Run:  .venv/bin/python .claude/skills/ct-carousel/scripts/ct_carousel.py <spec.json>
Out:  ~/Downloads/ct_<slug>_carousel_<date>/slide_01.png ...  +  reports/<slug>_carousel_<date>.html (overview)

Spec (JSON):
  slug          "job_change"               file-name stem
  date          "2026-11-20"
  article_url   full URL of the article     (shown nowhere on the slides; kept for the captions)
  title         ["dark line", "blue line"]  the article title split in two, as on the cover
  takeaways     [{"icon": <name in ICONS>, "headline": "...", "paragraphs": ["...", ...],
                  "list": ["...", ...] (optional, drawn as pale-blue chips after the first paragraph)}]
  cover_label   optional, default "<n> Key Takeaways"
  end_lines     optional, default ["Read the full article on", "ClearerThinking.org/Blog"]
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
ROOT = SKILL_DIR.parents[2]
sys.path.insert(0, str(ROOT / ".claude/skills/ct-infographic/scripts"))
import ct_infographic as kit  # noqa: E402

DEFAULT_END_LINES = ["Read the full article on", "ClearerThinking.org/Blog"]
SWIPE = "Swipe"

# ---- look (do not change without Igor's approval: every carousel must match) -------------------
FMT = kit.FORMATS["portrait"]          # 1600 x 2000 canvas
SCALE = 1080 / FMT["width"]            # export straight to Instagram's 1080 x 1350
MARGIN = 130
HEAD_PX, BODY_PX = 100, 60

S = 'fill="none" stroke="{c}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"'
INK, BLUE, ORANGE = kit.INK, kit.BLUE_RAMP[3], kit.ORANGE

# Flat icons on a 100 x 100 grid: blue line work (stroke 4), one orange detail each.
# A new carousel may ADD icons here in the same style; never restyle existing ones.
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

# Closing-slide owl: same flat line style as the icons (blue line work, orange details), perched on an open book.
OWL = (f'<svg class="owl" viewBox="0 0 240 262" width="400" height="437">'
       f'<path d="M66 92 L52 30 L104 56 Z M174 92 L188 30 L136 56 Z" fill="{kit.BLUE_RAMP[0]}" stroke="{BLUE}" stroke-width="6" stroke-linejoin="round"/>'
       f'<path d="M120 42 C182 42 202 100 202 150 C202 205 166 234 120 234 C74 234 38 205 38 150 C38 100 58 42 120 42 Z" '
       f'fill="{kit.BLUE_RAMP[0]}" stroke="{BLUE}" stroke-width="6"/>'
       f'<ellipse cx="120" cy="188" rx="48" ry="36" fill="#fff"/>'
       + "".join(f'<path d="M{x} {y} q6 7 12 0" {S.format(c=BLUE)} opacity=".55"/>'
                 for y, xs in [(176, (90, 108, 126, 144)), (196, (99, 117, 135))] for x in xs)
       + f'<path d="M50 142 C58 172 70 196 90 210 M190 142 C182 172 170 196 150 210" {S.format(c=BLUE)} stroke-width="6"/>'
       f'<circle cx="86" cy="112" r="34" fill="#fff" stroke="{BLUE}" stroke-width="6"/>'
       f'<circle cx="154" cy="112" r="34" fill="#fff" stroke="{BLUE}" stroke-width="6"/>'
       f'<circle cx="90" cy="116" r="16" fill="{INK}"/><circle cx="150" cy="116" r="16" fill="{INK}"/>'
       f'<circle cx="96" cy="109" r="5.5" fill="#fff"/><circle cx="156" cy="109" r="5.5" fill="#fff"/>'
       f'<circle cx="62" cy="150" r="9" fill="{ORANGE}" opacity=".3"/><circle cx="178" cy="150" r="9" fill="{ORANGE}" opacity=".3"/>'
       f'<path d="M110 136 H130 L120 154 Z" fill="{ORANGE}" stroke="{ORANGE}" stroke-width="4" stroke-linejoin="round"/>'
       f'<path d="M98 230 v10 M106 230 v10 M134 230 v10 M142 230 v10" {S.format(c=ORANGE)} stroke-width="6"/>'
       f'<path d="M40 238 Q80 226 120 240 Q160 226 200 238 V256 Q160 244 120 258 Q80 244 40 256 Z" fill="{ORANGE}"/>'
       f'<path d="M120 241 V256" stroke="#fff" stroke-width="4" stroke-linecap="round"/></svg>')

CSS = f"""
#canvas {{ position:relative; }}
.main {{ flex:1; display:flex; flex-direction:column; justify-content:flex-start; padding:190px {MARGIN}px 0; }}
.main.cover {{ justify-content:center; padding-top:0; }}
.badge {{ border-radius:50%; background:{kit.BLUE_RAMP[0]}; display:flex; align-items:center; justify-content:center; flex:none; }}
.label {{ font-size:32px; font-weight:600; text-transform:uppercase; letter-spacing:3.8px; opacity:.7; }}
.head {{ font-size:{HEAD_PX}px; font-weight:600; line-height:1.18; letter-spacing:-0.3px; text-wrap:balance; margin:0; }}
.rule {{ width:120px; height:6px; border-radius:3px; background:{ORANGE}; margin:60px 0 60px; }}
.body p {{ font-size:{BODY_PX}px; font-weight:400; line-height:1.5; margin:0 0 34px; text-wrap:pretty; }}
.list {{ display:flex; flex-direction:column; gap:16px; margin:6px 0 40px; }}
.list div {{ background:{kit.BLUE_RAMP[0]}; border-radius:12px; padding:24px 34px; font-size:{BODY_PX}px; font-weight:600; }}
.top {{ display:flex; align-items:center; gap:40px; margin-bottom:80px; }}
.dots {{ display:flex; gap:16px; justify-content:center; padding:0 0 56px; }}
.dots span {{ width:16px; height:16px; border-radius:50%; background:{kit.BLUE_RAMP[1]}; }}
.dots span.on {{ background:{ORANGE}; width:48px; border-radius:8px; }}
.cover {{ align-items:center; text-align:center; }}
.cover .t {{ font-size:124px; font-weight:600; line-height:1.14; letter-spacing:-0.5px; text-wrap:balance; }}
.cover .t .l2 {{ color:{kit.BLUE}; }}
.cover .label {{ margin-bottom:64px; }}
.row {{ display:flex; gap:28px; justify-content:center; margin-top:110px; }}
.swipe {{ margin-top:110px; font-size:34px; font-weight:600; color:{kit.BLUE}; display:flex; align-items:center; gap:18px; }}
.end .t {{ font-size:104px; }}
.end .owl {{ margin-bottom:70px; }}
.end .src {{ margin-top:72px; font-size:40px; font-style:italic; font-weight:500; opacity:.75; text-wrap:balance; }}
"""

ARROW = (f'<svg width="64" height="24" viewBox="0 0 64 24"><path d="M2 12 H58 M46 2 L60 12 L46 22" '
         f'{S.format(c=kit.BLUE)}/></svg>')

MAX_TAKEAWAYS = 8        # cover + 8 + end = 10 slides, Instagram's carousel limit
MAX_HEADLINE_CHARS = 75  # ~3 lines at 100 px
MAX_BODY_CHARS = 330     # paragraphs + list items; ~8 lines at 60 px still clear the dots


def validate(spec: dict) -> list[str]:
    """Problems that would break the layout or the house rules; empty list = OK."""
    errs = []
    for key in ("slug", "date", "title", "takeaways"):
        if key not in spec:
            errs.append(f"missing '{key}'")
    if errs:
        return errs
    if len(spec["title"]) != 2:
        errs.append("title must be two lines [dark, blue]")
    tks = spec["takeaways"]
    if not 1 <= len(tks) <= MAX_TAKEAWAYS:
        errs.append(f"{len(tks)} takeaways; allowed 1-{MAX_TAKEAWAYS}")
    for n, t in enumerate(tks, 1):
        if t.get("icon") not in ICONS:
            errs.append(f"takeaway {n}: unknown icon {t.get('icon')!r} (have {', '.join(ICONS)})")
        if len(t.get("headline", "")) > MAX_HEADLINE_CHARS:
            errs.append(f"takeaway {n}: headline over {MAX_HEADLINE_CHARS} characters")
        body = sum(len(p) for p in t.get("paragraphs", [])) + sum(len(x) for x in t.get("list") or [])
        if body > MAX_BODY_CHARS:
            errs.append(f"takeaway {n}: body {body} characters, over {MAX_BODY_CHARS}")
    text = json.dumps(spec, ensure_ascii=False)
    if "—" in text:
        errs.append("em dash found (house rule: none)")
    return errs


def icon(name: str, size: int) -> str:
    return (f'<div class="badge" style="width:{size}px;height:{size}px">'
            f'<svg viewBox="0 0 100 100" width="{size * 0.62:.0f}" height="{size * 0.62:.0f}">{ICONS[name]}</svg></div>')


def dots(current: int, total: int) -> str:
    return '<div class="dots">' + "".join(
        f'<span class="{"on" if i == current else ""}"></span>' for i in range(total)) + "</div>"


def cover_body(spec: dict, total: int) -> str:
    t1, t2 = spec["title"]
    label = spec.get("cover_label") or f"{len(spec['takeaways'])} Key Takeaways"
    return (f'<div class="main cover"><div class="label">{label}</div>'
            f'<div class="t"><div>{t1}</div><div class="l2">{t2}</div></div>'
            f'<div class="row">{"".join(icon(t["icon"], 150) for t in spec["takeaways"])}</div>'
            f'<div class="swipe">{SWIPE} {ARROW}</div></div>{dots(0, total)}')


def takeaway_body(spec: dict, i: int, total: int) -> str:
    t = spec["takeaways"][i]
    paras, items = t["paragraphs"], t.get("list")
    parts = [f"<p>{paras[0]}</p>"]
    if items:
        parts.append('<div class="list">' + "".join(f"<div>{x}</div>" for x in items) + "</div>")
    parts += [f"<p>{p}</p>" for p in paras[1:]]
    return (f'<div class="main"><div class="top">{icon(t["icon"], 210)}'
            f'<div class="label">Key takeaway {i + 1} of {len(spec["takeaways"])}</div></div>'
            f'<h1 class="head">{t["headline"]}</h1><div class="rule"></div>'
            f'<div class="body">{"".join(parts)}</div></div>{dots(i + 1, total)}')


def end_body(spec: dict, total: int) -> str:
    e1, e2 = spec.get("end_lines") or DEFAULT_END_LINES
    t1, t2 = spec["title"]
    return (f'<div class="main cover end">{OWL}<div class="t"><div>{e1}</div><div class="l2">{e2}</div></div>'
            f'<div class="src">“{t1} {t2}”</div>'
            f'</div>{dots(total - 1, total)}')


def slides(spec: dict) -> list[tuple[str, str]]:
    """(alt text, body html) for every slide, in order."""
    n = len(spec["takeaways"])
    total = n + 2
    e1, e2 = spec.get("end_lines") or DEFAULT_END_LINES
    out = [(f"Cover: {' '.join(spec['title'])}", cover_body(spec, total))]
    out += [(spec["takeaways"][i]["headline"], takeaway_body(spec, i, total)) for i in range(n)]
    out.append((f"{e1} {e2}", end_body(spec, total)))
    return out


def out_paths(spec: dict) -> tuple[Path, Path]:
    out_dir = Path.home() / "Downloads" / f"ct_{spec['slug']}_carousel_{spec['date']}"
    overview = ROOT / "reports" / f"{spec['slug']}_carousel_{spec['date']}.html"
    return out_dir, overview


def overview(spec: dict, paths: list[Path], out_dir: Path) -> str:
    imgs = "".join(f'<img src="{p.as_uri()}" alt="slide {n}">' for n, p in enumerate(paths, 1))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{spec['slug'].replace('_', ' ').title()} Carousel</title>
<style>body {{ margin:0; padding:32px; background:#eee; font-family:{kit.FONT_STACK}; color:{INK}; }}
h1 {{ font-size:24px; font-weight:600; margin:0 0 4px; }} .sub {{ color:#666; margin:0 0 24px; font-size:15px; }}
.strip {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(320px, 1fr)); gap:20px; }}
img {{ width:100%; border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,.12); background:#fff; }}</style></head>
<body><h1>Carousel: {' '.join(spec['title'])}</h1>
<p class="sub">{kit.timestamp()} · {len(paths)} slides, 1080 x 1350 · PNGs in {out_dir}</p>
<div class="strip">{imgs}</div></body></html>"""


def render(spec: dict) -> list[Path]:
    errs = validate(spec)
    if errs:
        raise SystemExit("Spec problems:\n  " + "\n  ".join(errs))
    out_dir, overview_path = out_paths(spec)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    paths = []
    for n, (alt, body) in enumerate(slides(spec), 1):
        png = out_dir / f"slide_{n:02d}.png"
        html = kit.page_html(body_html=body, css=CSS, width=FMT["width"], height=FMT["height"],
                             name=f"{spec['slug']} carousel, slide {n}", alt=alt, png_path=png)
        kit.export(html, tmp / f"slide_{n:02d}.html", png, width=FMT["width"], height=FMT["height"], scale=SCALE)
        paths.append(png)
    overview_path.write_text(overview(spec, paths, out_dir), encoding="utf-8")
    return paths + [overview_path]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print("\n".join(str(p) for p in render(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))))
