"""Save the public (free) version of a newsletter article as a Wix blog DRAFT.

The body comes from the members-only GuidedTrack program's *html blocks (the clean article
HTML that already exists in guidedtrack/), cut where the newsletter's paywall sits, then the
members-only call to action and the footnotes. Nothing below the footnotes (rating box, podcast
promo, footer) is included. Images must be in the Wix Media Manager first (ids in ARTICLE).

    .venv/bin/python wix_newsletter_draft.py            # build, print an outline, write nothing
    .venv/bin/python wix_newsletter_draft.py --create   # create the draft post (never publishes)

Needs WIX_API_KEY + WIX_SITE_ID in .env (see wix_publish_hub.py). The draft's byline is the
member in WIX_BLOG_MEMBER_ID (defaults to Igor's); set the real author in the Wix editor.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from wix_publish_hub import DEFAULT_MEMBER_ID, MAX_POST_BYTES, _call
import wix_ricos as wr

REPO = Path(__file__).resolve().parent

MEMBERS_URL = "https://programs.clearerthinking.org/members-only-content/?newsletter=The%20Supplement%20Paradox&src=supplement-paradox-web"

ARTICLE = {
    "title": "The Supplement Paradox: Why are so many claims about supplements B.S.?",
    "slug": "the-supplement-paradox",
    "excerpt": ("Two arguments for taking supplements sound compelling, yet large trials keep failing to "
                "find the benefits they promise. Spencer Greenberg and Travis M. on what the evidence "
                "actually supports."),
    "source": REPO / "guidedtrack" / "The Supplement Paradox (Members-Only).gt",
    # The free part ends with this text; the newsletter shows a faded preview and the paywall after it.
    "cut_after": "It seems to us that if:</p>",
    # ...and resumes with the footnotes, up to (not including) the coaching box.
    "resume_from": "<h2><strong>Footnotes</strong></h2>",
    "stop_before": '<div class="ct-coach">',
    # beehiiv image URL (as in the GT source) -> Wix media id + pixel size (UploadImageToWixSite, 2026-10-12)
    "images": {
        "180b9ee7-cf9b-4be1-a5e9-3f36ec6f4555/image4.png": ("3c0c4c_9056ab2004bc4ae6a18bd0382971c9aa~mv2.png", 1875, 839, "A capsule on a velvet table"),
        "ae51ee61-3759-440c-8a37-9568f597daf4/upload_ec04e78b1ff07d29.png": ("3c0c4c_6a17cfc63f074f019e0d565732028075~mv2.png", 680, 308, "Reasons people give for taking supplements, by age group"),
    },
    "cover": "3c0c4c_9056ab2004bc4ae6a18bd0382971c9aa~mv2.png",  # the hero image, shown once as the cover
    "fade": ("3c0c4c_9ba7338a4390404eb2bdf9929c051645~mv2.png", 513, 99, "The rest of the article is for members"),
    # Same wording as the paywall snippet in the beehiiv draft.
    "paywall": {
        "heading": "You’ve reached the members-only part of this article",
        "body": ("Almost everything we write is still completely free for everyone, but some articles (no more "
                 "than 1 per month) may have an extra section for paid members, whose support makes our work "
                 "possible. Members also get ad-free podcasts, early access to new tools, and more."),
        "button": "Become a member to read the rest",
        "url": MEMBERS_URL,
    },
}


def gt_html(source: Path, images: dict) -> str:
    """The *html blocks and *image lines of a GuidedTrack program as one HTML string, in order.

    <style> blocks are dropped; each *image becomes an <img> carrying its Wix media id.
    """
    parts: list[str] = []
    in_html = False
    for line in source.read_text().splitlines():
        if line.startswith("*html"):
            in_html = True
            continue
        if line.startswith("*image: "):
            in_html = False
            url = line[len("*image: "):].strip()
            key = next((k for k in images if url.endswith(k)), None)
            if key is None:
                # Fine as long as it falls in a part that gets cut; free_version_html checks.
                parts.append(f'<img data-missing="{url}">')
                continue
            media_id, w, h, alt = images[key]
            parts.append(f'<img data-id="{media_id}" data-w="{w}" data-h="{h}" alt="{alt}">')
            continue
        if in_html and line.startswith("\t"):
            parts.append(line[1:])
            continue
        if line.strip() == "" and in_html:
            continue
        in_html = False
    html = "\n".join(parts)
    html = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    return html


def free_version_html(article: dict) -> tuple[str, str]:
    """(free part, footnotes part) of the article HTML, title/thanks box/hero stripped from the body."""
    html = gt_html(article["source"], article["images"])
    for marker in ("cut_after", "resume_from", "stop_before"):
        if html.count(article[marker]) != 1:
            raise ValueError(f"{marker} marker found {html.count(article[marker])} times, expected 1")
    head, rest = html.split(article["cut_after"])
    head += article["cut_after"]
    foot = rest.split(article["resume_from"])[1].split(article["stop_before"])[0]
    foot = article["resume_from"] + foot
    # The members-only banner, the h1 (the post title) and the hero (the cover) do not belong in the body.
    head = re.sub(r'<div class="ct-thanks">.*?</div>', "", head, count=1, flags=re.S)
    head = re.sub(r"<h1 [^>]*>.*?</h1>", "", head, count=1, flags=re.S)
    head = re.sub(rf'<img data-id="{re.escape(article["cover"])}"[^>]*>', "", head, count=1)
    missing = re.search(r'data-missing="([^"]+)"', head + foot)
    if missing:
        raise ValueError(f"an image in the kept part has no Wix media id: {missing.group(1)}")
    return head, foot


def paywall_nodes(article: dict) -> list[dict]:
    fade_id, w, h, alt = article["fade"]
    pw = article["paywall"]
    return [
        wr.image(fade_id, w, h, alt),
        dict(wr.SPACER),
        wr.heading([wr.text_node(pw["heading"])], 3, center=True),
        wr.paragraph([wr.text_node(pw["body"])], center=True),
        wr.button(pw["button"], pw["url"]),
        wr.paragraph([wr.text_node("Already a paid subscriber? "), wr.text_node("Click here", bold=True, url=pw["url"]),
                      wr.text_node(" to read the full version.")], center=True),
        dict(wr.SPACER),
    ]


def build(article: dict) -> dict:
    head, foot = free_version_html(article)
    nodes = wr.with_spacers(wr.html_to_nodes(head)) + paywall_nodes(article) + wr.with_spacers(wr.html_to_nodes(foot))
    body = {"draftPost": {
        "title": article["title"],
        "excerpt": article["excerpt"],
        "richContent": {"nodes": nodes},
        "seoSlug": article["slug"],
        "commentingEnabled": True,
        "language": "en",
        "memberId": os.getenv("WIX_BLOG_MEMBER_ID", DEFAULT_MEMBER_ID),
        "media": {"wixMedia": {"image": {"id": article["cover"]}}, "displayed": True, "custom": True},
    }}
    size = len(json.dumps(body).encode())
    if size > MAX_POST_BYTES:
        raise RuntimeError(f"payload is {size:,} bytes, over the {MAX_POST_BYTES:,} byte limit")
    return body


def outline(nodes: list[dict]) -> str:
    lines = []
    for n in nodes:
        t = n["type"]
        if t in ("PARAGRAPH", "HEADING"):
            txt = "".join(r["textData"]["text"] for r in n.get("nodes", []))
            lines.append(f"{t[:4]}{n['headingData']['level'] if t == 'HEADING' else ''}  {txt[:90]}" if txt else "----  (spacer)")
        elif t in ("BULLETED_LIST", "ORDERED_LIST"):
            lines.append(f"LIST  {len(n['nodes'])} items")
        elif t == "BLOCKQUOTE":
            lines.append(f"QUOT  {wr.plain_text(n['nodes'])[:90]}")
        elif t == "IMAGE":
            lines.append(f"IMG   {n['imageData']['image']['src']['id']}")
        elif t == "BUTTON":
            lines.append(f"BTN   {n['buttonData']['text']} -> {n['buttonData']['link']['url']}")
        else:
            lines.append(t)
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--create", action="store_true", help="create the draft post on Wix")
    ap.add_argument("--json", type=Path, help="also write the request body here")
    args = ap.parse_args()

    body = build(ARTICLE)
    nodes = body["draftPost"]["richContent"]["nodes"]
    links = sum(1 for n in nodes if n["type"] in ("PARAGRAPH", "HEADING")
                for r in n.get("nodes", []) for d in r["textData"]["decorations"] if d["type"] == "LINK")
    print(outline(nodes))
    print(f"\n{len(nodes)} nodes, {links} inline links in top-level text, "
          f"{len(json.dumps(body).encode()) / 1024:.0f}KB, slug={body['draftPost']['seoSlug']}")
    if args.json:
        args.json.write_text(json.dumps(body, indent=1))
    if not args.create:
        print("dry run: nothing sent (pass --create)")
        return
    created = _call("POST", "/draft-posts?fieldsets=URL", body)["draftPost"]
    print(f"created draft {created['id']}  status={created['status']}  "
          f"editor: https://manage.wix.com/dashboard/{os.getenv('WIX_SITE_ID')}/blog/{created['id']}/edit")
    print(json.dumps({k: created.get(k) for k in ("title", "seoSlug", "url", "memberId", "minutesToRead")}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
