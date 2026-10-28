"""Render drip_copy.md as the HTML that Google Drive converts into a Google Doc.

Usage: python build_doc_html.py [--split]  -> writes drip_copy.html (or part1/part2) beside this file.
The converter is deliberately minimal (headings, paragraphs, bullet lists, bold, code, links,
"[Button: ...]" lines) so the Doc gets native Docs styles and nothing else.
"""
import html, pathlib, re, sys

SRC = pathlib.Path(__file__).with_name("drip_copy.md")


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
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
        if line == "---":
            out.append("<hr>")
        elif line.startswith("# "):
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
        elif re.match(r"^\d+\. ", line):
            out.append(f"<p>{inline(line)}</p>")
        elif line.startswith("[Button:") and line.endswith("]"):
            out.append(f'<p><b>[Button] {inline(line[8:-1].strip())}</b></p>')
        else:
            out.append(f"<p>{inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "<html><body>" + "\n".join(out) + "</body></html>"


if __name__ == "__main__":
    md = SRC.read_text()
    if "--split" in sys.argv:
        a, rest = md.split("### 1E.", 1)
        b_, c = rest.split("\n---\n\n## Email 2", 1)
        title = "# New Subscribers drip: personalized copy"
        parts = {
            "drip_copy_part1.html": a.replace(title, title + " (1 of 3: how to use it, Email 1 paths A to D)"),
            "drip_copy_part2.html": title + " (2 of 3: Email 1 paths E to H)\n\n### 1E." + b_,
            "drip_copy_part3.html": title + " (3 of 3: Emails 2 to 4, review notes)\n\n## Email 2" + c,
        }
    else:
        parts = {"drip_copy.html": md}
    for name, text in parts.items():
        out = SRC.with_name(name)
        out.write_text(render(text))
        print(name, len(out.read_text().encode()), "bytes")
