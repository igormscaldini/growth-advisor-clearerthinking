"""Give every Clearer Thinking article three related articles, using Wix Blog's own Related Posts setting.

Why: 457 of 626 articles have no link from another article (reports/blog_discoverability_followup_2026-11-18.html).
Wix shows a strip of three posts under every article, server-rendered, so its links are crawlable. With nothing
chosen it shows the three NEWEST posts on every page; a post's `relatedPostIds` (post settings -> Advanced ->
Related Posts in the dashboard) replaces them with up to three posts of our choosing. Setting that field links
articles to each other without touching anybody's prose.

How the three are chosen: a blend of two TF-IDF cosine similarities, one over what the article says it is about
(title, summary, headings) and one over its full text. Full text alone pairs long study write-ups with each other
on shared research vocabulary whatever their subject. Then a balanced assignment spreads the links: no article
collects more than CAP inbound links, every eligible article gets MIN_IN where a match above FLOOR exists, and no
pair below FLOOR is ever linked (a post may end with fewer than three).

    python related_posts.py --plan                 # compute, write reports/related_posts_plan.json, print stats
    python related_posts.py --preview              # the plan as reports/related_posts_preview_<date>.html
    python related_posts.py --apply --only <slug>  # set one post (test first)
    python related_posts.py --apply                # set every post in the plan that is safe to republish
    python related_posts.py --rollback             # put back what each post had before (from the ledger)

Safety: a post whose draft has unpublished changes is never published from here (that would push a teammate's
pending edit live); those are listed in the plan under "skipped". Only `relatedPostIds` is PATCHed.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
PLAN = ROOT / "reports" / "related_posts_plan.json"
LEDGER = ROOT / "reports" / "related_posts_applied.json"
SITE = "https://www.clearerthinking.org"
K = 3            # Wix allows up to three related posts
CAP = 5          # most inbound related links one article may collect
MIN_IN = 2       # every eligible article should receive at least this many, where a good enough match exists
FLOOR = 0.10     # a pair scoring below this is never linked: an empty slot beats an unrelated "read next"
TOPIC_SHARE = 0.6  # weight of the title + summary + headings match; the rest is the full-text match
TITLE_WEIGHT = 3
MIN_WORDS = 40   # a post with less body text than this is a stub (an empty "Test" post is live at /post/_test)
STOP = set("""a about above after again against all am an and any are as at be because been before being below between both but by can
could did do does doing down during each few for from further had has have having he her here hers herself him himself his how i if in
into is it its itself just me more most my myself no nor not now of off on once only or other our ours ourselves out over own same she
should so some such than that the their theirs them themselves then there these they this those through to too under until up very was
we were what when where which while who whom why will with would you your yours yourself yourselves also one two may many much like get
click here read our take your free clearer thinking clearerthinking""".split())


# --- pure helpers (tests/test_related_posts.py) -------------------------------------------------------
def tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z'’]{2,}", text.lower()) if w not in STOP]


def tfidf(docs: list[list[str]]) -> list[dict[str, float]]:
    """L2-normalised TF-IDF vectors (sublinear tf, smoothed idf). A term in a single document carries no
    similarity information and a term in every document none either, but both are kept: idf handles them."""
    n = len(docs)
    df = Counter(t for d in docs for t in set(d))
    out = []
    for d in docs:
        tf = Counter(d)
        vec = {t: (1 + math.log(c)) * (math.log((1 + n) / (1 + df[t])) + 1) for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        out.append({t: v / norm for t, v in vec.items()})
    return out


def cosine_all(vecs: list[dict[str, float]]) -> list[list[float]]:
    """Dense cosine matrix through an inverted index (630 documents: fast enough, no numpy needed)."""
    n = len(vecs)
    index = defaultdict(list)
    for i, v in enumerate(vecs):
        for t, w in v.items():
            index[t].append((i, w))
    sim = [[0.0] * n for _ in range(n)]
    for postings in index.values():
        if len(postings) > 1:
            for a in range(len(postings)):
                i, wi = postings[a]
                row = sim[i]
                for b in range(a + 1, len(postings)):
                    j, wj = postings[b]
                    row[j] += wi * wj
    for i in range(n):
        for j in range(i + 1, n):
            sim[j][i] = sim[i][j]
    return sim


def assign(sim: list[list[float]], candidates: dict[int, list[int]], k: int = K, cap: int = CAP,
           min_in: int = MIN_IN, floor: float = 0.0) -> dict[int, list[int]]:
    """Pick up to k targets for each source from its own candidate list: most similar first, links spread out.

    `candidates` maps each source to the targets it is allowed to link to. Pass 1 walks every allowed
    (source, target) pair from the most to the least similar and accepts it while the source has room and
    the target is under `cap`. Pass 2 lifts each target still under `min_in`: its most similar allowed
    source takes it, giving up the link whose target can best spare one. A source never links to itself,
    and no pair scoring under `floor` is linked in either pass. Deterministic: ties break on index.
    """
    out: dict[int, list[int]] = {s: [] for s in candidates}
    indeg: Counter = Counter()
    pairs = sorted(((sim[s][t], s, t) for s, ts in candidates.items() for t in ts if s != t and sim[s][t] >= floor),
                   key=lambda p: (-p[0], p[1], p[2]))
    for _, s, t in pairs:
        if len(out[s]) < k and indeg[t] < cap:
            out[s].append(t)
            indeg[t] += 1
    wanted_by = defaultdict(list)
    for s, ts in candidates.items():
        for t in ts:
            if s != t and sim[s][t] >= floor:
                wanted_by[t].append(s)
    for t in sorted(wanted_by, key=lambda t: (indeg[t], t)):
        while indeg[t] < min_in:
            move = None
            for s in sorted((s for s in wanted_by[t] if t not in out[s]), key=lambda s: (-sim[s][t], s)):
                if len(out[s]) < k:
                    move = (s, None)
                    break
                spare = [x for x in out[s] if indeg[x] > min_in]
                if spare:
                    move = (s, min(spare, key=lambda x: (sim[s][x], x)))
                    break
            if move is None:
                break
            s, drop = move
            if drop is not None:
                out[s].remove(drop)
                indeg[drop] -= 1
            out[s].append(t)
            indeg[t] += 1
    return {s: sorted(ts, key=lambda t: (-sim[s][t], t)) for s, ts in out.items()}


def blend(a: list[list[float]], b: list[list[float]], share: float) -> list[list[float]]:
    """share * a + (1 - share) * b, element by element."""
    return [[share * x + (1 - share) * y for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def is_glossary(slug: str) -> bool:
    return "definition-examples-and-effects" in slug


def eligible(post: dict, sitemap_urls: set[str], redirected_paths: set[str], hub_url: str) -> bool:
    """An article worth linking to: listed in the sitemap (so not noindexed or canonicalised away), not the
    index page itself, not a path that redirects elsewhere, and not an empty stub."""
    path = post["url"].replace(SITE, "")
    return (post["url"] in sitemap_urls and post["url"] != hub_url and path not in redirected_paths
            and len(post.get("text", "").split()) >= MIN_WORDS)


# --- Wix --------------------------------------------------------------------------------------------
def _wix():
    import wix_publish_hub as wix
    return wix


def _text(node, out):
    if isinstance(node, dict):
        if "textData" in node:
            out.append(node["textData"].get("text", ""))
        for v in node.values():
            _text(v, out)
    elif isinstance(node, list):
        for v in node:
            _text(v, out)
    return out


def headings(rich: dict | None) -> str:
    """Text of every HEADING node in a Ricos document."""
    return " ".join(" ".join(_text(n, [])) for n in (rich or {}).get("nodes", []) if n.get("type") == "HEADING")


def fetch_posts() -> list[dict]:
    wix, posts, off = _wix(), [], 0
    while True:
        res = wix._call("GET", f"/posts?paging.limit=50&paging.offset={off}&fieldsets=URL&fieldsets=RICH_CONTENT")
        batch = res.get("posts", [])
        for p in batch:
            posts.append({
                "id": p["id"], "slug": p["slug"], "title": p["title"],
                "url": (p.get("url") or {}).get("base", "") + (p.get("url") or {}).get("path", ""),
                "published": (p.get("firstPublishedDate") or "")[:10],
                "unpublished_changes": bool(p.get("hasUnpublishedChanges")),
                "related": p.get("relatedPostIds") or [],
                "text": re.sub(r"\s+", " ", " ".join(_text(p.get("richContent"), []))).strip(),
                "topic": " ".join([(p["title"] + " ") * TITLE_WEIGHT, p.get("excerpt") or "", headings(p.get("richContent"))]),
            })
        off += len(batch)
        if not batch or off >= res.get("metaData", {}).get("total", 0):
            return posts


def build_plan() -> dict:
    import seo_hub_pages as hub
    import tools_redirects as tr
    wix = _wix()
    posts = fetch_posts()
    sitemap = {e["url"] for e in hub.fetch_sitemap(hub.BLOG_SITEMAP)}
    redirected = tr.existing_from_paths()
    ok = [i for i, p in enumerate(posts) if eligible(p, sitemap, redirected, wix.HUB_URL)]
    sim = blend(cosine_all(tfidf([tokens(p["topic"]) for p in posts])),
                cosine_all(tfidf([tokens(p["title"] + " " + p["text"]) for p in posts])), TOPIC_SHARE)
    # Only posts that can be republished safely give links, so the spread is computed over links that will
    # really exist. Glossary entries may point at anything, but only other glossary entries point at them:
    # an article's three slots go to articles (a 300-word definition is a poor "read next" for a long piece).
    givers = [i for i in ok if not posts[i]["unpublished_changes"]]
    arts = [i for i in ok if not is_glossary(posts[i]["slug"])]
    chosen = assign(sim, {s: (ok if is_glossary(posts[s]["slug"]) else arts) for s in givers}, floor=FLOOR)
    indeg = Counter(t for ts in chosen.values() for t in ts)
    rows = []
    for i in ok:
        p = posts[i]
        rows.append({"id": p["id"], "slug": p["slug"], "title": p["title"], "url": p["url"], "published": p["published"],
                     "glossary": is_glossary(p["slug"]), "inbound": indeg[i], "current": p["related"],
                     "skip": "draft has unpublished changes" if p["unpublished_changes"] else None,
                     "related": [{"id": posts[t]["id"], "slug": posts[t]["slug"], "title": posts[t]["title"],
                                  "similarity": round(sim[i][t], 3)} for t in chosen.get(i, [])]})
    return {"generated": time.strftime("%Y-%m-%d %H:%M"), "k": K, "cap": CAP, "min_in": MIN_IN, "floor": FLOOR, "posts": rows,
            "not_eligible": [posts[i]["slug"] for i in range(len(posts)) if i not in set(ok)]}


def stats(plan: dict) -> dict:
    rows = plan["posts"]
    todo = [r for r in rows if not r["skip"]]
    sims = sorted(t["similarity"] for r in todo for t in r["related"])
    inb = Counter(r["inbound"] for r in rows)
    return {"articles": len(rows), "will_be_set": len(todo), "skipped_pending_edits": len(rows) - len(todo),
            "links_created": sum(len(r["related"]) for r in todo),
            "givers_with_fewer_than_3": sum(1 for r in todo if len(r["related"]) < plan["k"]),
            "inbound_distribution": dict(sorted(inb.items())),
            "similarity_median": sims[len(sims) // 2] if sims else None,
            "similarity_p10": sims[len(sims) // 10] if sims else None,
            "similarity_min": sims[0] if sims else None}


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("<", "&lt;").replace("\n", " ").strip()


def preview_markdown(plan: dict, priority: list[str] = ()) -> str:
    """The plan as a page a person can skim: totals, the weakest pairings, then every article with its three."""
    rows, st = plan["posts"], stats(plan)
    by_slug = {r["slug"]: r for r in rows}
    inbound = defaultdict(list)
    for r in rows:
        for t in r["related"]:
            inbound[t["slug"]].append((t["similarity"], r["title"]))
    weakest = sorted(((t["similarity"], r["title"], t["title"]) for r in rows for t in r["related"]))[:25]
    dist = ", ".join(f"{n} articles get {k}" for k, n in st["inbound_distribution"].items())
    md = [f"# Related articles: proposed pairings", "",
          f"**{st['will_be_set']} articles** would each show up to three related articles in the strip under the post, "
          f"**{st['links_created']} links** in all. Chosen by topic and text similarity, at most {plan['cap']} inbound links "
          f"per article, none below a similarity of {plan['floor']}. Inbound links after rollout: {dist}.", "",
          f"**{st['skipped_pending_edits']} articles are left alone** because their Wix draft has unpublished changes, "
          "and publishing them from here would push those edits live. They keep showing the three newest posts, and "
          "they still receive links.", "",
          "## The pairings to check first: the weakest 25", "",
          "| Score | Article | Would link to |", "|---|---|---|"]
    md += [f"| {a:.2f} | {_cell(b)} | {_cell(c)} |" for a, b, c in weakest]
    if priority:
        md += ["", "## The articles this was started for", "", "| Article | Shows | Is linked from |", "|---|---|---|"]
        for slug in priority:
            r = by_slug.get(slug)
            if r:
                shows = "<br>".join(_cell(t["title"]) for t in r["related"]) or "(nothing above the floor)"
                frm = "<br>".join(_cell(t) for _, t in sorted(inbound[slug], reverse=True)) or "(nothing above the floor)"
                md.append(f"| [{_cell(r['title'])}]({r['url']}) | {shows} | {frm} |")
    md += ["", "## Every article", "", "| Published | Article | Related 1 | Related 2 | Related 3 |", "|---|---|---|---|---|"]
    for r in sorted((r for r in rows if not r["skip"]), key=lambda r: r["published"], reverse=True):
        cells = [f"{_cell(t['title'])} ({t['similarity']:.2f})" for t in r["related"]] + [""] * (plan["k"] - len(r["related"]))
        md.append(f"| {r['published']} | [{_cell(r['title'])}]({r['url']}) | " + " | ".join(cells) + " |")
    md += ["", f"## Left alone: {st['skipped_pending_edits']} articles with unpublished draft changes", ""]
    md += [f"- {r['published']} [{_cell(r['title'])}]({r['url']})" for r in sorted((r for r in rows if r["skip"]), key=lambda r: r["published"], reverse=True)]
    return "\n".join(md)


def write_preview(plan: dict, priority: list[str] = ()) -> Path:
    sys.path.insert(0, str(ROOT / "reports"))
    from md_report import render_page, timestamp
    css = ("body{max-width:1180px}table{border-collapse:collapse;width:100%;font-size:13.5px}td,th{border-bottom:1px solid #e5e5e5;"
           "padding:6px 8px;text-align:left;vertical-align:top}th{font-size:12.5px;color:#666}a{word-break:normal}")
    out = ROOT / "reports" / f"related_posts_preview_{time.strftime('%Y-%m-%d')}.html"
    out.write_text(render_page(preview_markdown(plan, priority), "Related articles: proposed pairings", css,
                               extensions=("tables", "sane_lists"),
                               subtitle=f"{timestamp()} · plan computed {plan['generated']} · nothing here is live except the one test post"))
    return out


# The four articles to request indexing for, and the one Markus flagged (reports/blog_discoverability_followup_2026-11-18.html).
PRIORITY = ["a-better-way-to-ask-why-from-behavioral-science", "decision-advisor-a-randomized-controlled-trial-of-a-decision-making-tool",
            "how-to-understand-your-morality-using-data", "is-what-youve-been-taught-about-biases-wrong",
            "what-20-000-people-taught-us-about-entrepreneurship-and-startups"]


def apply(plan: dict, only: str | None = None, pause: float = 1.0) -> None:
    wix = _wix()
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    rows = [r for r in plan["posts"] if not only or r["slug"] == only]
    if only and not rows:
        raise SystemExit(f"{only} is not in the plan")
    done = skipped = 0
    for r in rows:
        want = [t["id"] for t in r["related"]]
        draft = wix._call("GET", f"/draft-posts/{r['id']}")["draftPost"]
        if draft.get("hasUnpublishedChanges"):          # re-checked live: the plan may be hours old
            print(f"  skip (pending edits): {r['slug']}")
            skipped += 1
            continue
        if (draft.get("relatedPostIds") or []) == want:
            continue
        ledger.setdefault(r["id"], {"slug": r["slug"], "before": draft.get("relatedPostIds") or []})
        wix._call("PATCH", f"/draft-posts/{r['id']}", {"draftPost": {"id": r["id"], "relatedPostIds": want}})
        wix._call("POST", f"/draft-posts/{r['id']}/publish")
        LEDGER.write_text(json.dumps(ledger, indent=1))
        done += 1
        print(f"  set {r['slug']} -> {', '.join(t['slug'][:40] for t in r['related'])}", flush=True)
        time.sleep(pause)
    print(f"{done} posts updated, {skipped} skipped for pending edits")


def rollback() -> None:
    wix = _wix()
    if not LEDGER.exists():
        print("no ledger, nothing to roll back")
        return
    ledger = json.loads(LEDGER.read_text())
    for pid, rec in list(ledger.items()):
        draft = wix._call("GET", f"/draft-posts/{pid}")["draftPost"]
        if draft.get("hasUnpublishedChanges"):
            print(f"  left alone (pending edits appeared since): {rec['slug']}")
            continue
        wix._call("PATCH", f"/draft-posts/{pid}", {"draftPost": {"id": pid, "relatedPostIds": rec["before"]}})
        wix._call("POST", f"/draft-posts/{pid}/publish")
        del ledger[pid]
        LEDGER.write_text(json.dumps(ledger, indent=1))
        print(f"  restored {rec['slug']}")
        time.sleep(1.0)
    if not ledger:
        LEDGER.unlink()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--preview", action="store_true", help="write the plan as an HTML page to skim")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--only")
    args = ap.parse_args()
    if args.rollback:
        rollback()
    elif args.plan:
        plan = build_plan()
        PLAN.write_text(json.dumps(plan, indent=1))
        print(json.dumps(stats(plan), indent=1))
    elif args.preview:
        print(write_preview(json.loads(PLAN.read_text()), PRIORITY))
    elif args.apply:
        if not PLAN.exists():
            sys.exit("run --plan first")
        apply(json.loads(PLAN.read_text()), args.only)
    else:
        ap.print_help()
