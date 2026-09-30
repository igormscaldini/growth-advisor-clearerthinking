"""Publish the "All Clearer Thinking Articles" link hub as a Wix blog post.

Why a blog post rather than a site page: Wix renders blog post BODY links server-side (verified
against /post/a-list-of-the-most-valuable-content-we-created-in-2022), and a post lands in
blog-posts-sitemap.xml automatically. A Wix HTML embed would render in an iframe, so its links
would not count as links from the page.

Why this exists at all: /blog paginates across 100 pages, exposes 3 article links per page, and
links to none of the other pages, so Googlebot reaches 4 pages and 12 of 621 articles. See
reports/seo_indexing_impact_2026-09-16.html.

Auth (https://dev.wix.com/docs/api-reference/articles/rest-authentication/rest-api-authentication):
an account owner generates an API key in the Wix dashboard with Blog permissions. Requests send
`Authorization: <key>` plus a `wix-site-id` header. Put both in .env (which is gitignored: this
repo is public).

    WIX_API_KEY=...
    WIX_SITE_ID=798e52ed-db7c-4e70-a25a-144134aae6c0

Usage:
    python wix_publish_hub.py --dry-run          # build the payload, print stats, call nothing
    python wix_publish_hub.py --create           # create the draft (unpublished)
    python wix_publish_hub.py --create --publish # create and publish it
    python wix_publish_hub.py --verify <url>     # count links in the live page's raw HTML
    python wix_publish_hub.py --delete-draft <id>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

import seo_hub_pages as hub

load_dotenv()

API_ROOT = "https://www.wixapis.com/blog/v3"
POST_TITLE = "All Clearer Thinking Articles"
# Backdated deliberately: this is an evergreen index, not a new article, so it should not sit at
# the top of the blog feed. Igor chose 2026-01-01.
FIRST_PUBLISHED_DATE = "2026-01-01T09:00:00.000Z"
# A single post is capped at 400KB by the Blog API.
MAX_POST_BYTES = 400 * 1024
# An API key has no member identity of its own, so the post owner must be named explicitly or
# the API returns "Missing post owner information". Defaults to Igor's member (nickname
# igormscaldini); the byline is publicly visible, so override it if the post should sit under a
# different author. The CT staff writers have their own member IDs.
DEFAULT_MEMBER_ID = "45fbd8aa-4a8f-42fe-afae-cdcfdaa2332f"
# The hub is itself a blog post, so it appears in blog-posts-sitemap.xml and would otherwise
# list itself.
HUB_URL = "https://www.clearerthinking.org/post/all-clearer-thinking-articles"


def _headers() -> dict:
    key, site = os.getenv("WIX_API_KEY"), os.getenv("WIX_SITE_ID")
    if not key or not site:
        raise RuntimeError("Set WIX_API_KEY and WIX_SITE_ID in .env (see this file's docstring).")
    return {"Authorization": key, "wix-site-id": site, "Content-Type": "application/json"}


def _call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{API_ROOT}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers=_headers(),
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode("utf-8", "ignore")
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:1500]
        raise RuntimeError(f"Wix API {method} {path} failed: HTTP {e.code}\n{detail}") from e


def build_payload() -> tuple[dict, int]:
    """Returns (request body, article count). All titles come from the cached page <title>s."""
    posts = [p for p in hub.enrich(hub.fetch_sitemap(hub.BLOG_SITEMAP))
             if p["url"].rstrip("/") != HUB_URL]
    intro = (f"Every article Clearer Thinking has published, {len(posts)} in total, "
             "grouped by year with the newest first.")
    body = {"draftPost": {
        "title": POST_TITLE,
        "excerpt": f"A complete index of all {len(posts)} Clearer Thinking articles, grouped by year.",
        "richContent": hub.render_ricos(intro, hub.group_by_year(posts)),
        "commentingEnabled": False,
        "language": "en",
        "firstPublishedDate": FIRST_PUBLISHED_DATE,
        "memberId": os.getenv("WIX_BLOG_MEMBER_ID", DEFAULT_MEMBER_ID),
    }}
    size = len(json.dumps(body).encode())
    if size > MAX_POST_BYTES:
        raise RuntimeError(f"Payload is {size:,} bytes, over the {MAX_POST_BYTES:,} byte post limit. "
                           "Split the hub across several posts.")
    return body, len(posts)


def find_hub_post() -> dict:
    """Locate the hub post by title rather than a hardcoded ID, so it survives a recreate."""
    if os.getenv("WIX_HUB_POST_ID"):
        return _call("GET", f"/draft-posts/{os.getenv('WIX_HUB_POST_ID')}?fieldsets=RICH_CONTENT&fieldsets=URL")["draftPost"]
    res = _call("POST", "/draft-posts/query", {
        "query": {"filter": {"title": {"$eq": POST_TITLE}}},
        "fieldsets": ["RICH_CONTENT", "URL"],
    })
    found = res.get("draftPosts", [])
    if len(found) != 1:
        raise RuntimeError(f"Expected exactly 1 draft post titled {POST_TITLE!r}, found {len(found)}. "
                           "Set WIX_HUB_POST_ID in .env to disambiguate.")
    return found[0]


def linked_urls(rich_content: dict) -> set[str]:
    """Every URL currently linked from a Ricos document."""
    out = set()
    for node in (rich_content or {}).get("nodes", []):
        for child in node.get("nodes", []):
            for dec in child.get("textData", {}).get("decorations", []):
                url = dec.get("linkData", {}).get("link", {}).get("url")
                if url:
                    out.add(url)
    return out


def verify(url: str, expected: int) -> int:
    """Fetch the live page as an ordinary client and count crawlable /post/ links.

    The whole point is server-rendered links, so this is the only check that matters. Wix serves
    a big SPA shell, so read the whole document rather than a prefix.
    """
    req = urllib.request.Request(url, headers={"User-Agent": hub.UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        html = r.read().decode("utf-8", "ignore")
    found = set(re.findall(r'<a[^>]+href="(https://www\.clearerthinking\.org/post/[^"]+)"', html))
    print(f"  {len(found)} crawlable /post/ links in raw HTML (expected around {expected})")
    return len(found)


def sync() -> tuple[str, str]:
    """Refresh the live hub with any newly published articles. Returns (subject, body).

    Skips the write entirely when nothing changed, so a quiet week costs one query and leaves
    the post's revision history clean.
    """
    body, total = build_payload()
    wanted = linked_urls(body["draftPost"]["richContent"])
    post = find_hub_post()
    live = linked_urls(post.get("richContent"))
    url = (post.get("url") or {}).get("base", "") + (post.get("url") or {}).get("path", "")

    added, removed = sorted(wanted - live), sorted(live - wanted)
    if not added and not removed:
        return (f"All Articles hub: no change ({total} articles)",
                f"Checked {total} articles in the sitemap. Nothing new since the last run, so the "
                f"post was left untouched.\n\n{url}\n")

    # PATCH only the fields that change. Leaving out firstPublishedDate, memberId, title and slug
    # means the backdate and byline survive the update.
    _call("PATCH", f"/draft-posts/{post['id']}", {"draftPost": {
        "id": post["id"],
        "richContent": body["draftPost"]["richContent"],
        "excerpt": body["draftPost"]["excerpt"],
    }})
    _call("POST", f"/draft-posts/{post['id']}/publish")

    after = find_hub_post()
    now_linked = len(linked_urls(after.get("richContent")))
    lines = [f"Updated the All Articles hub: {total} articles now linked "
             f"(was {len(live)}, the post reports {now_linked}).", "", url, ""]
    if added:
        lines.append(f"Added ({len(added)}):")
        lines += [f"  + {u}" for u in added]
    if removed:
        lines.append(f"\nRemoved ({len(removed)}), usually an unpublished or re-slugged post:")
        lines += [f"  - {u}" for u in removed]
    if now_linked != total:
        lines.append(f"\nWARNING: the post reports {now_linked} links but {total} were sent. "
                     "Check the post before trusting this run.")
    lines.append(f"\nfirstPublishedDate is still {after.get('firstPublishedDate')} "
                 "(the backdate should not move).")
    return f"All Articles hub: +{len(added)} article(s), {total} total", "\n".join(lines)


def _email(subject: str, body: str) -> None:
    import email_transport
    to = os.getenv("ADVISOR_EMAIL_TO") or email_transport.EMAIL_FROM
    try:
        email_transport.send_email(subject, body, to, header_tag="wix-hub-sync")
        print(f"emailed {to}: {subject}")
    except Exception as e:  # noqa: BLE001 - a failed notification must not mask the real result
        print(f"[warn] could not email the report: {e}", file=sys.stderr)
        email_transport.slack_fallback(str(e), "All Articles hub sync", email_transport.TRANSPORT_FIX)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--publish", action="store_true", help="publish the draft created by --create")
    ap.add_argument("--sync", action="store_true", help="refresh the live hub, then email the outcome")
    ap.add_argument("--no-email", action="store_true", help="with --sync, print the report instead")
    ap.add_argument("--verify", metavar="URL")
    ap.add_argument("--delete-draft", metavar="ID")
    args = ap.parse_args()

    if args.sync:
        try:
            subject, report = sync()
        except Exception as e:  # noqa: BLE001 - the whole point is to be told when it breaks
            import traceback
            detail = traceback.format_exc()
            print(detail, file=sys.stderr)
            if not args.no_email:
                _email("All Articles hub sync FAILED",
                       f"The weekly update of the All Articles hub did not run cleanly.\n\n"
                       f"{e}\n\nFull traceback:\n{detail}")
            raise SystemExit(1) from e
        print(subject)
        print(report)
        if not args.no_email:
            _email(subject, report)
        return

    if args.delete_draft:
        _call("DELETE", f"/draft-posts/{args.delete_draft}")
        print(f"deleted draft {args.delete_draft}")
        return

    if args.verify:
        verify(args.verify, expected=621)
        return

    body, n = build_payload()
    size = len(json.dumps(body).encode())
    nodes = body["draftPost"]["richContent"]["nodes"]
    links = sum(1 for x in nodes
                if x["type"] == "PARAGRAPH" and x["nodes"][0]["textData"]["decorations"])
    print(f"articles={n}  ricos nodes={len(nodes)}  linked paragraphs={links}  "
          f"payload={size:,} bytes ({size / 1024:.0f}KB of {MAX_POST_BYTES // 1024}KB)")
    print(f"firstPublishedDate={FIRST_PUBLISHED_DATE}")

    if args.dry_run or not args.create:
        Path("/tmp/wix_draft_body.json").write_text(json.dumps(body))
        print("dry run: payload written to /tmp/wix_draft_body.json, nothing sent")
        return

    created = _call("POST", "/draft-posts", body)["draftPost"]
    print(f"created draft {created['id']}  status={created['status']}  "
          f"firstPublishedDate={created.get('firstPublishedDate')}")

    if not args.publish:
        print("not published (pass --publish to publish it)")
        return

    post_id = _call("POST", f"/draft-posts/{created['id']}/publish")["postId"]
    print(f"published postId={post_id}")


if __name__ == "__main__":
    main()
