"""Render a partner copy file (gwwc.md, farmkind.md) as the minimal HTML that Google Drive converts into a
Google Doc with native heading styles. Usage: python build_doc_html.py gwwc.md -> gwwc.html beside it.
Same converter as reports/welcome_drip_copy_2026-10-28_src/build_doc_html.py (headings, paragraphs, bullets,
bold, links); the emoji headlines survive as plain text."""
import html
import pathlib
import re
import sys


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return s


def render(md: str) -> str:
    out, in_list = [], False
    for raw in md.splitlines():
        line = raw.rstrip()
        if in_list and not line.startswith("- "):
            out.append("</ul>")
            in_list = False
        if not line.strip():
            continue
        if line.startswith("# "):
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(line[2:])}</li>")
        else:
            out.append(f"<p>{inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "<html><body>" + "\n".join(out) + "</body></html>"


if __name__ == "__main__":
    for name in sys.argv[1:]:
        src = pathlib.Path(__file__).with_name(name)
        dst = src.with_suffix(".html")
        dst.write_text(render(src.read_text()))
        print(f"{dst} ({dst.stat().st_size:,} bytes)")
