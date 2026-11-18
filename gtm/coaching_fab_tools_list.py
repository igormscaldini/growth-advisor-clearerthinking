"""Keep the "Get Coaching" floating button's page list in step with the tools page.

The button (gtm/coaching_fab_tools.html, a GTM Custom HTML tag) shows only on the tools listed on
https://www.clearerthinking.org/clearer-thinking-tools (Igor, 2026-11-18). That page is the source of the list;
this script reads its tool cards and writes one path per tool between the BEGIN TOOLS / END TOOLS markers of the
snippet. GTM is not updated by this: after a change, paste the snippet into the tag and publish.

    python gtm/coaching_fab_tools_list.py           # compare the live page with the snippet (exit 1 if they differ)
    python gtm/coaching_fab_tools_list.py --write   # rewrite the list in the snippet
"""
from __future__ import annotations

import argparse
import concurrent.futures
import html
import re
import sys
import urllib.parse
from pathlib import Path

import requests

TOOLS_PAGE = "https://www.clearerthinking.org/clearer-thinking-tools"
TOOLS_HOST = "programs.clearerthinking.org"          # the only host the GTM tag runs the button on
SNIPPET = Path(__file__).with_name("coaching_fab_tools.html")
BEGIN, END = "// BEGIN TOOLS", "// END TOOLS"
# Wix serves the complete server-rendered page (all cards) to a crawler user agent.
CRAWLER_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

# Listed on the tools page but deliberately left without the button: normalized path -> reason.
KEEP_OFF = {
    "/cognitive-test-intro": "paid product page, no competing CTA (Igor, 2026-11-10)",
}


def normalize_path(path: str) -> str:
    """The form the snippet compares: lower-case, no trailing slash, no /index.html, no .html.
    Must stay identical to the `path` expression in the snippet (tests run both)."""
    path = path.lower().rstrip("/")
    path = re.sub(r"/index(\.html)?$", "", path)
    path = re.sub(r"\.html$", "", path)
    return path.rstrip("/")


def parse_cards(page_html: str) -> list[tuple[str, str]]:
    """(title, link) of every tool card: a card is a heading followed by its "Start" link."""
    cards = []
    for m in re.finditer(r'<a\b[^>]*?href="([^"]+)"[^>]*>(.*?)</a>', page_html, re.S):
        if _text(m.group(2)) != "Start":
            continue
        headings = re.findall(r"<h[1-6][^>]*>(.*?)</h[1-6]>", page_html[max(0, m.start() - 6000):m.start()], re.S)
        cards.append((_text(headings[-1]) if headings else "", html.unescape(m.group(1))))
    return cards


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def tool_entries(cards: list[tuple[str, str]], keep_off: dict[str, str] = KEEP_OFF) -> list[tuple[str, str]]:
    """Sorted (normalized path, title) of the cards that live on TOOLS_HOST, minus `keep_off`."""
    entries = {}
    for title, link in cards:
        url = urllib.parse.urlsplit(link)
        if url.netloc.lower() != TOOLS_HOST:
            continue
        path = normalize_path(urllib.parse.unquote(url.path))
        if path and path not in keep_off:
            entries.setdefault(path, title)
    return sorted(entries.items())


def render_block(entries: list[tuple[str, str]], keep_off: dict[str, str] = KEEP_OFF, indent: str = "      ") -> str:
    """The lines that go between the markers (markers included). No comma after the last entry: ES5-safe."""
    width = max((len(path) for path, _ in entries), default=0) + 3
    lines = [f"{indent}{BEGIN} (written by gtm/coaching_fab_tools_list.py, do not edit by hand)"]
    for n, (path, title) in enumerate(entries):
        code = f"'{path}'" + ("," if n < len(entries) - 1 else "")
        lines.append(f"{indent}{code.ljust(width)} // {title}")
    for path, reason in sorted(keep_off.items()):
        lines.append(f"{indent}// kept off on purpose: {path}: {reason}")
    lines.append(f"{indent}{END}")
    return "\n".join(lines)


def split_snippet(snippet: str) -> tuple[str, str, str]:
    """(before, block, after) where block runs from the BEGIN line to the END line, both whole."""
    m = re.search(rf"^[ \t]*{re.escape(BEGIN)}.*?^[ \t]*{re.escape(END)}[^\n]*$", snippet, re.S | re.M)
    if not m:
        raise ValueError(f"markers {BEGIN!r} / {END!r} not found in the snippet")
    return snippet[:m.start()], m.group(0), snippet[m.end():]


def block_entries(block: str) -> list[tuple[str, str]]:
    """(path, title) of each entry line of a block, in order (comment-only lines ignored)."""
    found = (re.match(r"\s*'([^']+)',?\s*//\s*(.*)$", line) for line in block.splitlines())
    return [(m.group(1), m.group(2).strip()) for m in found if m]


def fetch_cards() -> list[tuple[str, str]]:
    """The live cards, each link followed through its redirects so the list holds the path actually served."""
    page = requests.get(TOOLS_PAGE, headers={"User-Agent": CRAWLER_UA}, timeout=60)
    page.raise_for_status()
    cards = parse_cards(page.text)

    def served(card):
        title, link = card
        if urllib.parse.urlsplit(link).netloc.lower() != TOOLS_HOST:
            return card
        r = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        return title, r.url

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(served, cards))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true", help="rewrite the list in the snippet")
    args = ap.parse_args()

    cards = fetch_cards()
    entries = tool_entries(cards)
    elsewhere = [title for title, link in cards if urllib.parse.urlsplit(link).netloc.lower() != TOOLS_HOST]
    print(f"{len(cards)} tools on the page: {len(entries)} get the button, {len(KEEP_OFF)} kept off on purpose, "
          f"{len(elsewhere)} on other sites ({', '.join(elsewhere)})")
    if len(entries) < 50:
        print("Fewer than 50 tools found: the page probably did not render fully. Nothing changed.")
        return 1

    snippet = SNIPPET.read_text(encoding="utf-8")
    before, block, after = split_snippet(snippet)
    current, wanted = {path for path, _ in block_entries(block)}, {path for path, _ in entries}
    for path in sorted(wanted - current):
        print(f"  + {path}  ({dict(entries)[path]})")
    for path in sorted(current - wanted):
        print(f"  - {path}")
    new_block = render_block(entries)
    if new_block == block:
        print("The snippet matches the tools page.")
        return 0
    if not args.write:
        print("The snippet differs from the tools page. Run with --write, then paste the snippet into GTM.")
        return 1
    SNIPPET.write_text(before + new_block + after, encoding="utf-8")
    print(f"Rewrote the list in {SNIPPET.name}. Paste the snippet into the GTM tag and publish.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
