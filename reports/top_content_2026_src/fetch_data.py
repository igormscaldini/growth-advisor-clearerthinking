"""Pull the raw inputs for the 2026 top-articles ranking into data/ (aggregates only, no personal data).

wix_posts.json   every Wix blog post (id, slug, title, url, firstPublishedDate)
beehiiv_posts.json every confirmed beehiiv post published in 2026 (subject, title, web url, email stats)
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
import data_layer  # noqa: E402
import wix_publish_hub as wix  # noqa: E402

OUT = Path(__file__).parent / "data"
YEAR_START = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()


def wix_posts():
    posts, off = [], 0
    while True:
        res = wix._call("GET", f"/posts?paging.limit=100&paging.offset={off}&fieldsets=URL")
        batch = res.get("posts", [])
        for p in batch:
            posts.append({"id": p["id"], "slug": p["slug"], "title": p["title"],
                          "url": (p.get("url") or {}).get("base", "") + (p.get("url") or {}).get("path", ""),
                          "first_published": p.get("firstPublishedDate") or ""})
        off += len(batch)
        if not batch or off >= res.get("metaData", {}).get("total", 0):
            return posts


def beehiiv_posts():
    key, pub = os.environ["BEEHIIV_API_KEY"], os.environ["BEEHIIV_PUB_CLEARER_THINKING"]
    h = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    out, page = [], 1
    while True:  # filter on status only and page through everything (CLAUDE.md gotcha)
        r = data_layer._beehiiv_get(f"{data_layer.BEEHIIV_BASE}/publications/{pub}/posts", headers=h,
                                    params={"page": page, "limit": 100, "expand[]": "stats", "status": "confirmed"})
        r.raise_for_status()
        d = r.json()
        for p in d.get("data", []):
            if (p.get("publish_date") or 0) >= YEAR_START:
                em = (p.get("stats") or {}).get("email") or {}
                out.append({"id": p["id"], "publish_date": p["publish_date"], "title": p.get("title"),
                            "subject_line": p.get("subject_line"), "web_url": p.get("web_url"),
                            "custom_live_url": p.get("custom_live_url") or (p.get("meta_default_title") and None),
                            "platform": p.get("platform"), "audience": p.get("audience"),
                            "recipients": em.get("recipients"), "unique_opens": em.get("unique_opens"),
                            "opens": em.get("opens"), "unique_clicks": em.get("unique_clicks")})
        if page >= d.get("total_pages", 1):
            return out
        page += 1


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    w = wix_posts()
    (OUT / "wix_posts.json").write_text(json.dumps(w, indent=1))
    b = beehiiv_posts()
    (OUT / "beehiiv_posts.json").write_text(json.dumps(b, indent=1))
    print(len(w), "wix posts;", sum(p["first_published"] >= "2026" for p in w), "first published in 2026;", len(b), "beehiiv posts in 2026")
