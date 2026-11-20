"""Instagram quote post (4:5, 1080 x 1350) for Clearer Thinking Podcast episode 328.

The quote is verbatim from the episode transcript (checked by `check_verbatim` against
transcript_excerpt.txt). The ten candidates and the ten-agent vote are in quotes_and_votes.md.

Run: .venv/bin/python reports/podcast_quote_ep328_2026-11-20_src/build.py
Out: ~/Downloads/ct_podcast_quote_ep328.png + reports/podcast_quote_ep328_2026-11-20.html
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / ".claude/skills/ct-infographic/scripts"))
import ct_infographic as kit  # noqa: E402

SPEAKER = "Spencer Greenberg"
EPISODE = "Episode 328: Is it intent or impact that matters in our relationships?"
# Igor's pick (2026-11-20) after rejecting the vote winner ("light gassing"): candidate B.
QUOTE = ("Sometimes we want there to be this dichotomy: either you're a victim and there's nothing you "
         "can do, or you're not a victim. But actually, you can be a victim, and also there's something "
         "you can do, and actually there's something you really should do just for your own benefit.")
HIGHLIGHT = "you can be a victim, and also there's something you can do"  # drawn in CT blue; words unchanged
URL = "www.clearerthinking.org/podcast"

FMT = kit.FORMATS["portrait"]          # 1600 x 2000 canvas
SCALE = 1080 / FMT["width"]


def check_verbatim() -> None:
    transcript = (HERE / "transcript_excerpt.txt").read_text(encoding="utf-8")
    if QUOTE not in transcript:
        raise SystemExit("Quote is not verbatim in the transcript excerpt.")


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


def quote_html() -> str:
    before, after = QUOTE.split(HIGHLIGHT)
    return (html.escape(curly(before)) + f'<span class="hl">{html.escape(curly(HIGHLIGHT))}</span>'
            + html.escape(curly(after)))


CSS = f"""
.main {{ flex:1; display:flex; flex-direction:column; justify-content:center; padding:0 150px; }}
.top {{ display:flex; justify-content:center; padding-top:120px; }}
.top .logo {{ height:70px; }}
.mark {{ font-family:Georgia, "Times New Roman", serif; font-size:300px; line-height:.6; height:150px;
         color:{kit.ORANGE}; margin-left:-12px; }}
.q {{ font-size:74px; font-weight:600; line-height:1.28; letter-spacing:-0.4px; text-wrap:pretty; margin:0; }}
.q .hl {{ color:{kit.BLUE}; }}
.rule {{ width:120px; height:6px; border-radius:3px; background:{kit.ORANGE}; margin:84px 0 52px; }}
.who {{ font-size:46px; line-height:1.4; text-wrap:balance; margin:0; }}
.who b {{ font-weight:600; }}
.who .ep {{ opacity:.72; }}
.footer {{ height:150px; }}
.url {{ font-size:46px; font-weight:600; color:{kit.BLUE}; letter-spacing:.3px; }}
"""


def body() -> str:
    return f"""
<div class="top">{kit.logo_markup()}</div>
<div class="main">
  <div class="mark">“</div>
  <p class="q">{quote_html()}</p>
  <div class="rule"></div>
  <p class="who"><b>{SPEAKER}</b> on the Clearer Thinking Podcast,
     <span class="ep">“{html.escape(EPISODE)}”</span></p>
</div>"""


def main() -> None:
    check_verbatim()
    png = Path.home() / "Downloads/ct_podcast_quote_ep328.png"
    preview = ROOT / "reports/podcast_quote_ep328_2026-11-20.html"
    page = kit.page_html(body_html=body(), css=CSS, width=FMT["width"], height=FMT["height"],
                         name="Podcast quote, episode 328", png_path=png,
                         alt=f"{curly(QUOTE)} {SPEAKER} on the Clearer Thinking Podcast, {EPISODE}. {URL}")
    # The kit's footer carries the logo; this post carries the podcast URL there instead (logo sits on top).
    page = page.replace(f'<div class="footer">{kit.logo_markup()}</div>',
                        f'<div class="footer"><div class="url">{URL}</div></div>')
    kit.export(page, preview, png, width=FMT["width"], height=FMT["height"], scale=SCALE)
    print(png, preview, sep="\n")


if __name__ == "__main__":
    main()
