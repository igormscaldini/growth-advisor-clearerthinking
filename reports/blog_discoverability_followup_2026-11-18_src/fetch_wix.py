"""Pull every published Wix blog post (slug, dates, categories, tags) and the category list.

Writes data/wix_posts.json. Needs WIX_API_KEY + WIX_SITE_ID in .env (see wix_publish_hub.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent))

import wix_publish_hub as wix  # noqa: E402

KEEP = ("id", "title", "slug", "firstPublishedDate", "lastPublishedDate", "categoryIds", "tagIds",
        "relatedPostIds", "minutesToRead", "memberId")


def all_posts() -> list[dict]:
    out, offset = [], 0
    while True:
        res = wix._call("GET", f"/posts?paging.limit=100&paging.offset={offset}&fieldsets=URL")
        batch = res.get("posts", [])
        out += [{**{k: p.get(k) for k in KEEP},
                 "url": (p.get("url") or {}).get("base", "") + (p.get("url") or {}).get("path", "")}
                for p in batch]
        offset += len(batch)
        if not batch or offset >= res.get("metaData", {}).get("total", 0):
            return out


if __name__ == "__main__":
    data = {"categories": wix._call("GET", "/categories?paging.limit=100").get("categories", []),
            "posts": all_posts()}
    (HERE / "data").mkdir(exist_ok=True)
    (HERE / "data" / "wix_posts.json").write_text(json.dumps(data, indent=1))
    print(f"{len(data['posts'])} posts, {len(data['categories'])} categories")
