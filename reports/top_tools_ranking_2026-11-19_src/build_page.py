"""data.json -> reports/top_tools_ranking_2026-11-19.html, the page published on GitHub Pages.

    .venv/bin/python reports/top_tools_ranking_2026-11-19_src/build_page.py [--window 12m|ytd|90d] [--partner-copies]

--partner-copies adds the visitors of partner-branded copies (/p/<partner>/<tool>/) to each tool. Default: left out.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "reports"), str(ROOT / ".claude/skills/ct-infographic/scripts")]

import ranking as R  # noqa: E402
from ct_infographic import BLUE, FONT_STACK, INK, ORANGE, logo_markup  # noqa: E402  (CT palette + logo, one source)
from md_report import timestamp  # noqa: E402

OUT = ROOT / "reports/top_tools_ranking_2026-11-19.html"
TOOLS_PAGE = "https://www.clearerthinking.org/clearer-thinking-tools"
# Typos in the Airtable short descriptions, fixed for display only (wrong -> right).
TYPOS = {"custome report": "custom report"}


def first_sentence(text: str) -> str:
    """The first sentence of a tool's short description, ending in punctuation."""
    text = re.sub(r"\s+", " ", text or "").strip()
    for wrong, right in TYPOS.items():
        text = text.replace(wrong, right)
    if not text:
        return ""
    sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return sentence if sentence[-1] in ".!?" else sentence + "."


def long_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}, {d.year}"


def top_rows(data: dict, window: str, variant: str) -> list[dict]:
    """The ranked rows of one window: own pages only (variant "own") or with partner copies ("with_partner")."""
    w = data["windows"][window]
    users = {b: t[variant]["users"] for b, t in w["tools"].items() if "users" in t[variant]}
    rows = []
    for n, (base, count) in enumerate(R.rank(users, data["top_n"]), 1):
        tool = data["tools"][base]
        launched = tool.get("launch_date") or ""
        rows.append({"rank": n, "name": tool["name"], "url": tool["url"], "users": count,
                     "description": first_sentence(tool.get("description", "")),
                     "tag": f"New in {launched[:4]}" if launched >= w["start"] else ""})
    return rows


def notes(data: dict, window: str, variant: str) -> list[str]:
    w = data["windows"][window]
    period = f"{long_date(w['start'])} and {long_date(w['end'])}"
    partner = ("Visitors of partner-branded copies of a tool count toward that tool."
               if variant == "with_partner" else "Partner-branded copies of a tool are not counted.")
    left_out = data.get("excluded") or []
    not_ranked = f" Not ranked: {' and '.join(left_out)}." if left_out else ""
    return [
        f"Unique users are the people who opened a tool's page at least once between {period}, "
        "according to Google Analytics. Each person counts once per tool, however many times they came back.",
        f"Ranked: {len(data['tools'])} tools from the <a href=\"{TOOLS_PAGE}\">Clearer Thinking tools page</a>, "
        f"all hosted on {data['host']}. {partner}{not_ranked}",
        "The numbers include visitors brought by ads, not only regular traffic.",
        "The Ultimate Personality Test is undercounted: since July 21, 2026 its page only reports visitors who "
        "press Start, and nothing was recorded from July 22 to August 10, 2026.",
    ]


def render(data: dict, window: str = "12m", variant: str = "own", now: datetime | None = None) -> str:
    w = data["windows"][window]
    rows = top_rows(data, window, variant)
    items = "\n".join(
        f'''    <li>
      <span class="rank">{r["rank"]}</span>
      <div class="what">
        <a class="name" href="{html.escape(r["url"])}">{html.escape(r["name"])}</a>{f' <span class="tag">{r["tag"]}</span>' if r["tag"] else ""}
        <p class="desc">{html.escape(r["description"])}</p>
      </div>
      <span class="users">{r["users"]:,}</span>
    </li>''' for r in rows)
    note_items = "\n".join(f"      <li>{n}</li>" for n in notes(data, window, variant))
    n = len(rows)
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Clearer Thinking: {n} most popular tools</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #fff; color: {INK}; font-family: {FONT_STACK}; line-height: 1.45;
         -webkit-font-smoothing: antialiased; }}
  main {{ max-width: 760px; margin: 0 auto; padding: 40px 20px 64px; }}
  .logo {{ height: 34px; width: auto; display: block; margin-bottom: 40px; }}
  h1 {{ font-size: clamp(28px, 6vw, 42px); line-height: 1.12; letter-spacing: -0.01em; margin: 0 0 12px; }}
  h1 span {{ color: {BLUE}; }}
  .sub {{ color: #6b7280; font-size: 15px; margin: 0 0 34px; }}
  .head {{ display: flex; justify-content: space-between; color: #6b7280; font-size: 12px; font-weight: 600;
           letter-spacing: 0.08em; text-transform: uppercase; padding: 0 0 10px 58px; }}
  ol {{ list-style: none; margin: 0; padding: 0; border-top: 1px solid #e8e8e8; }}
  ol li {{ display: grid; grid-template-columns: 44px 1fr auto; column-gap: 14px; align-items: start;
           padding: 18px 0; border-bottom: 1px solid #e8e8e8; }}
  .rank {{ font-size: 26px; font-weight: 700; line-height: 1.1; color: {BLUE}; font-variant-numeric: tabular-nums; }}
  .name {{ font-size: 18px; font-weight: 600; color: {INK}; text-decoration: none; }}
  .name:hover, .name:focus {{ color: {BLUE}; text-decoration: underline; }}
  .tag {{ display: inline-block; margin-left: 6px; padding: 1px 8px; border: 1px solid {ORANGE}; border-radius: 999px;
          color: #b4540f; font-size: 11.5px; font-weight: 600; white-space: nowrap; vertical-align: 2px; }}
  .desc {{ margin: 4px 0 0; color: #6b7280; font-size: 14.5px; }}
  .users {{ font-size: 20px; font-weight: 700; line-height: 1.3; font-variant-numeric: tabular-nums; white-space: nowrap;
            text-align: right; }}
  .notes {{ margin-top: 40px; color: #6b7280; font-size: 13.5px; }}
  .notes h2 {{ margin: 0 0 8px; color: {INK}; font-size: 14px; }}
  .notes ul {{ margin: 0; padding-left: 18px; }}
  .notes li {{ margin-bottom: 6px; }}
  .notes a {{ color: inherit; }}
  @media (max-width: 520px) {{
    main {{ padding: 28px 16px 48px; }}
    ol li {{ grid-template-columns: 30px 1fr auto; column-gap: 10px; }}
    .head {{ padding-left: 40px; }}
    .rank {{ font-size: 21px; }}
    .name {{ font-size: 16.5px; }}
    .users {{ font-size: 17px; }}
  }}
</style>
</head>
<body>
<main>
  <a href="https://www.clearerthinking.org/" aria-label="Clearer Thinking">{logo_markup()}</a>
  <h1>Clearer Thinking's <span>{n} most popular tools</span></h1>
  <p class="sub">Ranked by unique users, {long_date(w["start"])} to {long_date(w["end"])}. Updated {timestamp(now)}.</p>
  <div class="head"><span>Tool</span><span>Unique users</span></div>
  <ol>
{items}
  </ol>
  <section class="notes">
    <h2>How this is counted</h2>
    <ul>
{note_items}
    </ul>
  </section>
</main>
</body>
</html>
'''


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--window", default="12m", choices=["12m", "ytd", "90d"])
    ap.add_argument("--partner-copies", action="store_true", help="count partner-branded copies toward each tool")
    args = ap.parse_args()
    data = json.loads((HERE / "data.json").read_text(encoding="utf-8"))
    variant = "with_partner" if args.partner_copies else "own"
    if not data["windows"][args.window]["certain"][variant]:
        raise SystemExit("A tool without an exact count could still belong in the top: raise `extra` in pick_candidates.")
    OUT.write_text(render(data, args.window, variant), encoding="utf-8")
    for r in top_rows(data, args.window, variant):
        print(f"{r['rank']:2d}. {r['name']:36s} {r['users']:>10,}  {r['tag']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
