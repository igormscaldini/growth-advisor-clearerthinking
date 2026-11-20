"""Clearer Thinking Podcast quote post: transcript -> 10 verbatim candidates -> 10-agent vote -> 4:5 PNG.

Commands (run from the repo root with .venv/bin/python):
  fetch [episode_url]      latest episode when no URL; writes reports/podcast_quote_ep<N>_<date>_src/
                           transcript.txt (gitignored) + spec.json (episode block, empty candidates)
  verify  <spec.json>      every candidate must appear word for word in transcript.txt
  ballots <spec.json>      the 10 shuffled candidate orders, one per voter (seeded, reproducible)
  tally   <spec.json>      first-place votes and 3/2/1 points from spec["votes"]
  render  <spec.json>      the chosen quote -> ~/Downloads/ct_podcast_quote_ep<N>.png + preview HTML

Spec (JSON):
  episode     {"number": 328, "title": "Is it ...?", "url": "...", "speakers": {"SPENCER": "Spencer Greenberg", ...}}
  candidates  [{"id": "A", "speaker": "Spencer Greenberg", "text": "verbatim"}, ...]   (10)
  votes       [{"vote": "A", "ranking": ["A", "B", "D"]}, ...]                         (10)
  chosen      "B"                    the candidate Igor picked
  highlight   optional substring of the chosen quote drawn in CT blue (words unchanged)
"""
from __future__ import annotations

import html
import json
import random
import re
import sys
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
ROOT = SKILL_DIR.parents[2]
sys.path.insert(0, str(ROOT / ".claude/skills/ct-infographic/scripts"))
import ct_infographic as kit  # noqa: E402

PODCAST = "https://podcast.clearerthinking.org"
URL_TEXT = "www.clearerthinking.org/podcast"
N_VOTERS = 10
MAX_WORDS = 55          # above this the text gets too small for a phone; ask Igor to pick a shorter one

# ---- look (approved by Igor on 2026-11-20, episode 328; change only with his OK) ----------------
FMT = kit.FORMATS["portrait"]          # 1600 x 2000 canvas
SCALE = 1080 / FMT["width"]            # export straight to Instagram's 1080 x 1350
CSS = f"""
.main {{ flex:1; display:flex; flex-direction:column; justify-content:center; padding:0 150px; }}
.top {{ display:flex; justify-content:center; padding-top:120px; }}
.top .logo {{ height:70px; }}
.mark {{ font-family:Georgia, "Times New Roman", serif; font-size:300px; line-height:.6; height:150px;
         color:{kit.ORANGE}; margin-left:-12px; }}
.q {{ font-weight:600; letter-spacing:-0.4px; margin:0; }}
.q .hl {{ color:{kit.BLUE}; }}
.rule {{ width:120px; height:6px; border-radius:3px; background:{kit.ORANGE}; margin:84px 0 52px; }}
.who {{ font-size:46px; line-height:1.4; text-wrap:balance; margin:0; }}
.who b {{ font-weight:600; }}
.who .ep {{ opacity:.72; }}
.footer {{ height:150px; }}
.url {{ font-size:46px; font-weight:600; color:{kit.BLUE}; letter-spacing:.3px; }}
"""


def quote_style(text: str) -> str:
    """Type size by length. Chrome only balances short paragraphs, so long ones use `pretty` (no orphans)."""
    n = len(text.split())
    if n <= 25:
        return "font-size:96px; line-height:1.24; text-wrap:balance;"
    if n <= 38:
        return "font-size:84px; line-height:1.26; text-wrap:pretty;"
    return "font-size:74px; line-height:1.28; text-wrap:pretty;"


# ---- transcript -------------------------------------------------------------------------------
def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def latest_episode_url(home_html: str) -> str:
    m = re.search(r'href="(/episode/\d+/[^"]+)"', home_html)
    if not m:
        raise SystemExit("No episode link found on the podcast home page.")
    return PODCAST + m.group(1)


def page_text(page_html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", page_html, flags=re.S)
    t = re.sub(r"<(br|/p|/div|/h\d|/li)[^>]*>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\n\s*\n+", "\n\n", t)


def parse_episode(text: str, url: str) -> dict:
    """Number, title (without the '(with ...)' tail) and a speaker-label -> full-name map."""
    m = re.search(r"Episode (\d+): (.+?) \(with (.+?)\)\s*$", text, re.M)
    if not m:
        raise SystemExit("Could not find 'Episode N: Title (with Guest)' on the page.")
    guests = re.split(r",\s*|\s+and\s+", m.group(3))
    speakers = {"SPENCER": "Spencer Greenberg"}
    speakers.update({g.split()[0].upper(): g for g in guests if g})
    return {"number": int(m.group(1)), "title": m.group(2).strip(), "url": url, "speakers": speakers}


def transcript_lines(text: str, speakers: dict) -> str:
    """Only the 'NAME: words' turns, one per line, so `verify` searches spoken words only."""
    labels = "|".join(map(re.escape, speakers))
    return "\n".join(ln.strip() for ln in text.splitlines() if re.match(rf"\s*({labels}):", ln)) + "\n"


def src_dir(number: int, day: str | None = None) -> Path:
    return ROOT / f"reports/podcast_quote_ep{number}_{day or date.today().isoformat()}_src"


def fetch(url: str | None = None) -> Path:
    url = url or latest_episode_url(_get(PODCAST + "/"))
    text = page_text(_get(url))
    ep = parse_episode(text, url)
    out = src_dir(ep["number"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "transcript.txt").write_text(transcript_lines(text, ep["speakers"]), encoding="utf-8")
    spec_path = out / "spec.json"
    if not spec_path.exists():
        spec_path.write_text(json.dumps({"episode": ep, "candidates": [], "votes": [], "chosen": ""},
                                        indent=1, ensure_ascii=False), encoding="utf-8")
    return out


# ---- candidates and vote ----------------------------------------------------------------------
def missing_quotes(spec: dict, transcript: str) -> list[str]:
    """Ids of candidates not found word for word (a capitalised first letter of a mid-sentence cut is allowed)."""
    bad = []
    for c in spec["candidates"]:
        t = c["text"]
        if t not in transcript and (t[0].lower() + t[1:]) not in transcript:
            bad.append(c["id"])
    return bad


def ballots(spec: dict, n: int = N_VOTERS) -> list[list[dict]]:
    out = []
    for v in range(1, n + 1):
        order = spec["candidates"][:]
        random.Random(v).shuffle(order)
        out.append(order)
    return out


def ballot_text(order: list[dict]) -> str:
    return "\n".join(f'{c["id"]} ({c["speaker"].split()[0]}): "{c["text"]}"' for c in order)


def tally(votes: list[dict]) -> list[tuple[str, int, int]]:
    """[(id, first-place votes, 3/2/1 points)], best first (votes, then points)."""
    firsts = Counter(v["vote"] for v in votes)
    points = Counter()
    for v in votes:
        for pts, cid in zip((3, 2, 1), v["ranking"]):
            points[cid] += pts
    ids = set(firsts) | set(points)
    return sorted(((i, firsts[i], points[i]) for i in ids), key=lambda r: (-r[1], -r[2], r[0]))


# ---- render -----------------------------------------------------------------------------------
def curly(text: str) -> str:
    """Typographic quotes and apostrophes only; no word changes."""
    out, open_q = [], True
    for ch in text:
        if ch == '"':
            out.append("“" if open_q else "”")
            open_q = not open_q
        elif ch == "'":
            out.append("’")
        else:
            out.append(ch)
    return "".join(out)


def quote_html(text: str, highlight: str = "") -> str:
    if not highlight:
        return html.escape(curly(text))
    if text.count(highlight) != 1:
        raise SystemExit("highlight must appear exactly once in the chosen quote.")
    before, after = text.split(highlight)
    return (html.escape(curly(before)) + f'<span class="hl">{html.escape(curly(highlight))}</span>'
            + html.escape(curly(after)))


def episode_label(ep: dict) -> str:
    return f'Episode {ep["number"]}: {ep["title"]}'


def chosen(spec: dict) -> dict:
    found = [c for c in spec["candidates"] if c["id"] == spec.get("chosen")]
    if not found:
        raise SystemExit('Set "chosen" to the id of the quote Igor picked.')
    return found[0]


def body(spec: dict) -> str:
    c = chosen(spec)
    return f"""
<div class="top">{kit.logo_markup()}</div>
<div class="main">
  <div class="mark">“</div>
  <p class="q" style="{quote_style(c["text"])}">{quote_html(c["text"], spec.get("highlight", ""))}</p>
  <div class="rule"></div>
  <p class="who"><b>{html.escape(c["speaker"])}</b> on the Clearer Thinking Podcast,
     <span class="ep">“{html.escape(episode_label(spec["episode"]))}”</span></p>
</div>"""


def render(spec_path: Path) -> list[Path]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    c = chosen(spec)
    if len(c["text"].split()) > MAX_WORDS:
        raise SystemExit(f"Quote is over {MAX_WORDS} words: ask Igor for a shorter one (never cut it silently).")
    transcript = spec_path.with_name("transcript.txt")
    if transcript.exists() and missing_quotes({"candidates": [c]}, transcript.read_text(encoding="utf-8")):
        raise SystemExit("The chosen quote is not word for word in transcript.txt.")
    n = spec["episode"]["number"]
    png = Path.home() / f"Downloads/ct_podcast_quote_ep{n}.png"
    preview = ROOT / f"reports/{spec_path.parent.name.removesuffix('_src')}.html"
    alt = f'{curly(c["text"])} {c["speaker"]} on the Clearer Thinking Podcast, {episode_label(spec["episode"])}. {URL_TEXT}'
    page = kit.page_html(body_html=body(spec), css=CSS, width=FMT["width"], height=FMT["height"],
                         name=f"Podcast quote, episode {n}", alt=html.escape(alt), png_path=png)
    # The kit's footer carries the logo; this post carries the podcast URL there (the logo sits on top).
    page = page.replace(f'<div class="footer">{kit.logo_markup()}</div>',
                        f'<div class="footer"><div class="url">{URL_TEXT}</div></div>')
    kit.export(page, preview.with_suffix(".tmp.html"), png, width=FMT["width"], height=FMT["height"], scale=SCALE)
    preview.with_suffix(".tmp.html").replace(preview)
    return [png, preview]


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit(__doc__)
    cmd, args = argv[0], argv[1:]
    if cmd == "fetch":
        print(fetch(args[0] if args else None))
        return
    spec_path = Path(args[0])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if cmd == "verify":
        bad = missing_quotes(spec, spec_path.with_name("transcript.txt").read_text(encoding="utf-8"))
        for c in spec["candidates"]:
            print(c["id"], "MISSING" if c["id"] in bad else "verbatim", f'{len(c["text"].split())} words')
        if bad:
            raise SystemExit(1)
    elif cmd == "ballots":
        for v, order in enumerate(ballots(spec), 1):
            print(f"=== VOTER {v} ===\n{ballot_text(order)}\n")
    elif cmd == "tally":
        for cid, firsts, pts in tally(spec["votes"]):
            print(f"{cid}  first-place {firsts}  points {pts}")
    elif cmd == "render":
        print("\n".join(map(str, render(spec_path))))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
