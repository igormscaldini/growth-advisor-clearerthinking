"""Shared Markdown -> standalone HTML page for the reports/*_src builders.

One source for the page shell, the base CSS and the subtitle timestamp format, so each report's builder only
supplies its Markdown, its title and any extra CSS.
"""
from datetime import datetime

import markdown

BASE_CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;color:#222;line-height:1.55;font-size:17px}
h1{font-size:30px;line-height:1.2;margin-bottom:6px}
h1+p{color:#666;font-size:15px;margin-top:0}
h2{font-size:24px;margin-top:48px;border-top:1px solid #e5e5e5;padding-top:24px}
h3{font-size:19px;margin-top:28px}
li{margin:6px 0}
ol li{padding-left:4px}
a{color:#1a5fb4;word-break:break-all}
strong{color:#111}
"""


def timestamp(now=None):
    """Report subtitle timestamp, yyyy-mm-dd hh:mm[am/pm] (e.g. 2026-11-06 03:05pm)."""
    now = now or datetime.now()
    return now.strftime("%Y-%m-%d %I:%M") + now.strftime("%p").lower()


def render_page(md_text, title, extra_css="", extensions=("sane_lists", "toc"), subtitle=None):
    """Return a complete HTML document for md_text. `subtitle` (plain text) is placed right under the first h1."""
    body = markdown.markdown(md_text, extensions=list(extensions))
    if subtitle:
        head, sep, tail = body.partition("</h1>")
        if not sep:
            raise ValueError("subtitle needs a level-1 heading to sit under")
        body = f"{head}{sep}\n<p>{subtitle}</p>{tail}"
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{title}</title><style>{BASE_CSS}{extra_css}</style></head><body>{body}</body></html>")
