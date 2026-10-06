"""Render the audience breakdown as a PDF in Clearer Thinking's visual style, from the same content()
as index.html (build_page.py), so the two never drift. The look is the personas report's: CT logo, Avenir,
CT blue bars on hairline tracks, navy headings, A4 printed by Chrome.

    .venv/bin/python reports/ct_sponsor_audience_report_2026-10-06_src/build_pdf.py

HTML to reports/ct_audience_breakdown_2026-10-06.html, PDF to ~/Downloads.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HTML_OUT = ROOT / "reports" / "ct_audience_breakdown_2026-10-06.html"
PDF_OUT = Path.home() / "Downloads" / "Clearer Thinking audience breakdown 2026-10-06.pdf"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pr = load("personas_report", ROOT / "reports" / "ct_audience_personas_2026-09-25_src" / "build_report.py")
bp = load("audience_page", HERE / "build_page.py")
esc = pr.esc


def bars(s: dict) -> str:
    return pr.bars(s["title"], [(r["label"], r["count"]) for r in s["rows"]], n=s["n"], sub=s["question"], note=s["note"])


def row(r: list) -> str:
    cells = ["".join(bars(s) for s in cell) for cell in r]
    return pr.grid(*cells) if len(cells) == 2 else cells[0]


def heading(sec: dict) -> str:
    return f'<div class="h2">{esc(sec["title"])}</div>' + (f'<p class="sub">{esc(sec["lead"])}</p>' if sec["lead"] else "")


def section(sec: dict, rows: list[int] | None = None) -> str:
    chosen = sec["rows"] if rows is None else [sec["rows"][i] for i in rows]
    return heading(sec) + "".join(row(r) for r in chosen)


def build_html(stamp: str) -> str:
    c = bp.content()
    who, working, reading, where = c["sections"]
    header = (f'<img class="logo" src="data:image/png;base64,{pr.logo_b64()}" alt="Clearer Thinking">'
              f'<h1>{esc(c["title"])}</h1><div class="meta">Data as of {stamp} · {esc(c["meta"])}</div>')
    summary = pr.callout("In short", "<ul>" + "".join(f"<li>{b}</li>" for b in c["summary"]) + "</ul>")
    # Three balanced A4 pages; the third "Who they are" row (politics, education) opens page 2.
    pages = [header + summary + section(who, rows=[0, 1]),
             row(who["rows"][2]) + section(working),
             section(reading) + section(where)]
    body = "".join(f'<div class="page">{p}</div>' for p in pages)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{esc(c["title"])}</title>
<style>{pr.CSS}{EXTRA_CSS}</style></head>
<body>{body}</body></html>"""


EXTRA_CSS = """
.logo{height:6.5mm;width:auto;margin:0 0 6mm;display:block}
h1{font-size:22pt;line-height:1.1;color:var(--navy);margin:0 0 1.5mm;font-weight:700;letter-spacing:-.01em}
.meta{font-size:9pt;color:var(--muted);margin:0 0 5mm}
.callout li{margin-bottom:1.2mm}
.h2{margin-top:7mm}
.h2:first-child{margin-top:0}
/* the last chart row on a page must not push its bottom margin onto a blank page */
.page > :last-child .chart:last-child,.page > .chart:last-child{margin-bottom:0}
"""


def main() -> None:
    stamp = dt.datetime.now().strftime("%Y-%m-%d %I:%M%p").replace("AM", "am").replace("PM", "pm")
    HTML_OUT.write_text(build_html(stamp))
    pr.render_pdf(HTML_OUT, PDF_OUT, stamp, footer_label="Audience breakdown")
    print(f"html: {HTML_OUT}\npdf:  {PDF_OUT}")


if __name__ == "__main__":
    main()
