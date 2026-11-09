"""Render "reports/Large newsletter list management.md" to reports/large_newsletter_list_management_2026-11-09.html.

The Markdown is the single source for every word and number. This builder only adds presentation: the timestamp
subtitle, a score badge on each recommendation heading and an at-a-glance table built from those same headings.
Research notes and the CT audit behind the report: research_notes/Large newsletter list management/.
"""
import re
import sys
from pathlib import Path

REPORTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPORTS))
from md_report import render_page, timestamp  # noqa: E402

SRC = REPORTS / "Large newsletter list management.md"
OUT = REPORTS / "large_newsletter_list_management_2026-11-09.html"

REC_HEADING = re.compile(r"^### (\d+)\. (.+)$", re.M)
ANY_HEADING = re.compile(r"^#{1,6} ", re.M)
SCORE = re.compile(r"\*\*Score: (\d+)/10\.\*\*")

EXTRA_CSS = """
body{max-width:920px}
a{word-break:normal;overflow-wrap:anywhere}
table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.45;margin:18px 0}
th{text-align:left;font-weight:600;color:#555;border-bottom:2px solid #ddd;padding:8px 10px}
td{vertical-align:top;border-bottom:1px solid #eee;padding:9px 10px}
code{font-size:.88em;background:#f5f5f5;padding:1px 4px;border-radius:3px}
.score{display:inline-block;font-size:13px;font-weight:700;padding:2px 9px;border-radius:11px;margin-right:6px;vertical-align:middle;white-space:nowrap}
.score.hi{background:#e3f3e8;color:#1c6b36}
.score.mid{background:#fcf1d2;color:#7a5a00}
.score.lo{background:#eeeeee;color:#666}
"""


def band(score):
    """Badge colour band: 7+ strong, 5-6 worthwhile, 4 or less not recommended."""
    return "hi" if score >= 7 else "mid" if score >= 5 else "lo"


def verdict(score):
    """The report adopts ideas scored 5 or more and leaves the rest alone."""
    return "Adopt" if score >= 5 else "Leave alone"


def recommendations(md):
    """[(number, name, score)] in document order. Each '### N. Name' block must hold exactly one 'Score: X/10.'"""
    out = []
    for h in REC_HEADING.finditer(md):
        nxt = ANY_HEADING.search(md, h.end())
        block = md[h.end():nxt.start() if nxt else len(md)]
        scores = SCORE.findall(block)
        if len(scores) != 1:
            raise ValueError(f"recommendation {h.group(1)} has {len(scores)} score lines, expected 1")
        out.append((int(h.group(1)), h.group(2).strip(), int(scores[0])))
    return out


def badge(score):
    return f'<span class="score {band(score)}">{score}/10</span>'


def glance_table(recs):
    """Markdown table linking to each recommendation (anchors rec-N are set by with_badges)."""
    rows = ["| Score | Recommendation | Verdict |", "|---|---|---|"]
    rows += [f"| {badge(s)} | [{n}. {name}](#rec-{n}) | {verdict(s)} |" for n, name, s in recs]
    return "\n".join(rows)


def with_badges(md):
    """Put the score badge and a stable anchor on every recommendation heading, and the glance table before the first."""
    recs = recommendations(md)
    by_number = {n: s for n, _, s in recs}

    def heading(m):
        n = int(m.group(1))
        return f"### {badge(by_number[n])} {n}. {m.group(2).strip()} {{: #rec-{n} }}"

    first = REC_HEADING.search(md)
    if not first:
        raise ValueError("no recommendation headings found")
    head, tail = md[:first.start()], md[first.start():]
    return f"{head}{glance_table(recs)}\n\n{REC_HEADING.sub(heading, tail)}"


def build():
    md = SRC.read_text()
    title = md.splitlines()[0].lstrip("# ").strip()
    subtitle = (f"{timestamp()} · How newsletters above a million subscribers run their lists and sends, "
                "set against a read-only audit of CT's beehiiv account (2026-11-06)")
    OUT.write_text(render_page(with_badges(md), title, EXTRA_CSS,
                               extensions=("tables", "sane_lists", "toc", "attr_list", "md_in_html"),
                               subtitle=subtitle))
    return OUT


if __name__ == "__main__":
    print(build())
