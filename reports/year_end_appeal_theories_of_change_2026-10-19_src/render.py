"""Render theories_of_change.md to the HTML report next to this folder, and copy the Markdown to ~/Downloads."""
import shutil
from pathlib import Path
import markdown

SRC = Path(__file__).parent / "theories_of_change.md"
OUT = Path(__file__).parent.parent / "year_end_appeal_theories_of_change_2026-10-19.html"
DOWNLOADS = Path.home() / "Downloads" / "CT_year-end_appeal_theories_of_change_2026-10-19.md"

CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;color:#222;line-height:1.55;font-size:17px}
h1{font-size:30px;line-height:1.2;margin-bottom:6px}
h1+p{color:#666;font-size:15px;margin-top:0}
h2{font-size:24px;margin-top:48px;border-top:1px solid #e5e5e5;padding-top:24px}
h3{font-size:19px;margin-top:28px}
li{margin:6px 0}
ol li{padding-left:4px}
a{color:#1a5fb4;word-break:break-all}
strong{color:#111}
h2#sources + ol{font-size:14px;color:#444}
"""
html_body = markdown.markdown(SRC.read_text(), extensions=["sane_lists", "toc"])
OUT.write_text(f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
               f"<title>Year-end appeal: theories of change</title><style>{CSS}</style></head><body>{html_body}</body></html>")
shutil.copy(SRC, DOWNLOADS)
print(OUT)
print(DOWNLOADS)
