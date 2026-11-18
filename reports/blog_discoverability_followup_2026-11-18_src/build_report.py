"""Render reports/blog_discoverability_followup_2026-11-18.html from datapoints.json (run analysis.py first)."""
from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import charts  # noqa: E402
import page  # noqa: E402
from md_report import timestamp  # noqa: E402

OUT = HERE.parent / "blog_discoverability_followup_2026-11-18.html"
HUB = "https://www.clearerthinking.org/post/all-clearer-thinking-articles"
INDEXED = ("Submitted and indexed", "Indexed, not submitted in sitemap")


def slug(u: str) -> str:
    return u.split("/post/", 1)[-1]


def link(u: str, text: str | None = None) -> str:
    return f'<a href="{escape(u)}">{escape(text or slug(u))}</a>'


def chip(kind: str, label: str) -> str:
    return f'<span class="chip {kind}"><i></i>{escape(label)}</span>'


def tile(label: str, value: str, note: str) -> str:
    return f'<div class="tile"><div class="label">{label}</div><div class="value">{value}</div><div class="note">{note}</div></div>'


def coverage_parts(cov: dict) -> list[dict]:
    indexed = sum(n for k, n in cov.items() if k in INDEXED)
    disc = cov.get("Discovered - currently not indexed", 0)
    crawled = cov.get("Crawled - currently not indexed", 0)
    other = sum(cov.values()) - indexed - disc - crawled
    return [{"label": "Indexed", "value": indexed, "slot": 1},
            {"label": "Discovered, not indexed (Google knows the URL, has not fetched it)", "value": disc, "slot": 2},
            {"label": "Crawled, not indexed (fetched and declined)", "value": crawled, "slot": 3},
            {"label": "Other (soft 404, duplicate, redirect, unknown)", "value": other, "slot": 4, "ink": "#0b0b0b"}]


def build(d: dict) -> str:
    L, C, T, I, S, M, B = d["links"], d["categories"], d["tools"], d["index"], d["search"], d["markus_article"], d["index"]["baseline"]
    mk = d["markus_claims"]
    dup = [p for p in d["duplicates"]["numbered_pairs"] if p["same_title"]]
    dup_both_indexed = sum(1 for p in dup if p["base"]["coverage"] in INDEXED and p["copy"]["coverage"] in INDEXED)
    dup_one_indexed = sum(1 for p in dup if (p["base"]["coverage"] in INDEXED) != (p["copy"]["coverage"] in INDEXED))
    dup_none = len(dup) - dup_both_indexed - dup_one_indexed
    feed = L["blog_feed"].get("/blog", {})
    hub_only, other = L["buckets"].get("hub_only", 0), L["buckets"].get("other_pages", 0)
    research_links = L["category_pages"].get("research", 0)
    redirected = sum(n for k, n in T["by_status"].items() if k in ("301", "302", "308"))
    not_idx = I["articles"] - I["indexed"]
    bt = d["baseline_timing"]
    before, latest = S["before_hub"], S["latest"]

    body = []
    body.append(f"""
<div class="verdict">
<p><b>The article Markus flagged is indexed, and so is {I['pct_indexed']:.0f}% of the blog.</b> Of his six findings, three (no crawlable archive, posts with no internal link, posts unreachable from the blog page) are closed by one workaround: the <a href="{HUB}">All Clearer Thinking Articles</a> page, which links all {L['hub']['links_in_raw_html']} articles in plain HTML and sits in the site menu on every page. The orphan <code>/tools/</code> pages are closed by redirects. Two are exactly where they were in July: {C['pct_without']}% of posts have no category, and the {len(dup)} duplicated glossary posts are still live.</p>
<p>The honest limit: the fix gave every article a way in, not a reason to rank. {hub_only} of {L['articles']} articles are linked from the hub and from nothing else, and {not_idx} articles are still not indexed.</p>
</div>
<div class="tiles">
{tile("Articles Google has indexed", f"{I['indexed']} <small>of {I['articles']}</small>", f"{I['pct_indexed']}%, per Search Console URL Inspection today")}
{tile("Posts not indexed in August, indexed now", f"{B['posts_now_indexed']} <small>of {B['posts']}</small>", "the tracking sheet's blog posts, re-inspected")}
{tile("Articles with no internal link at all", f"{len(L['zero_inbound_including_hub'])} <small>was {mk['zero_inbound']}</small>", f"but {hub_only} have only the hub link")}
{tile("Markus's article", "Indexed", f"{M['since_email']['impressions']:,} impressions and {M['since_email']['clicks']} clicks since his email")}
</div>""")

    rows = [
        ("1. Blog archive has no crawlable pagination",
         f"Googlebot reaches about {mk['blog_feed_links']} posts from /blog; {mk['posts']} posts affected",
         f"/blog itself is unchanged: {feed.get('post_links_excl_chrome', '?')} article links in raw HTML and no link to page 2. The hub replaces it: {L['hub']['links_in_raw_html']} article links, on {L['hub_on_share_of_posts'] * 100:.0f}% of pages through the menu.",
         chip("around", "Worked around")),
        ("2. Posts with no category",
         f"{mk['no_category']} of {mk['posts']} (95.7%)",
         f"{C['without_category']} of {C['posts']} ({C['pct_without']}%). Nothing was done, on purpose: a category page server-renders only its first {research_links} posts, so categories cannot carry {C['posts']} articles.",
         chip("same", "Unchanged")),
        ("3. Posts with zero inbound internal links",
         f"{mk['zero_inbound']}",
         f"{len(L['zero_inbound_including_hub'])}. Every article has the hub link. For {hub_only} of them it is the only one; {other} are also linked from another article or page.",
         chip("good", "Fixed, thinly")),
        ("4. Posts unreachable from the blog index",
         f"{mk['unreachable_from_blog']} (infinite scroll stopped at 300 posts)",
         "0 through the hub, which is one click from any page. The scroll limit on /blog was not re-tested and nothing suggests Wix changed it.",
         chip("around", "Worked around")),
        ("5. /tools/ pages nothing links to",
         f"{mk['tools_unlinked']} of {mk['tools_pages']}",
         f"{redirected} of the {T['in_sitemap']} still listed in the sitemap now 301 to the real tool; {len(T['still_200'])} still answer 200. They were thin copies of tools that already rank, so linking to them would have been the wrong fix.",
         chip("good", "Fixed by redirect")),
        ("6. Duplicate posts at /slug and /slug-1",
         f"about {mk['duplicate_pairs']} pairs, each self-canonical",
         f"{len(dup)} pairs, all still live and self-canonical, all from the 2021 bias glossary. Google indexes both copies of {dup_both_indexed}, one copy of {dup_one_indexed} and neither of {dup_none}.",
         chip("open", "Still open")),
    ]
    body.append("<h2>Scorecard: the six findings</h2><div class='scroll'><table class='score'><thead><tr><th>Markus's finding</th><th>July 30 (his crawl)</th><th>Today</th><th>Status</th></tr></thead><tbody>"
                + "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{s}</td></tr>" for a, b, c, s in rows) + "</tbody></table></div>")

    q = "".join(f"<tr><td>{escape(r['query'])}</td><td class='num'>{r['impressions']}</td><td class='num'>{r['clicks']}</td><td class='num'>{r['position']}</td></tr>" for r in M["top_queries_since_oct"])
    refs = ", ".join(link(u, "the hub" if u.rstrip("/") == HUB else u.replace("https://www.clearerthinking.org", "")) for u in M["referring_urls"]) or "none reported"
    body.append(f"""
<h2>The article Markus flagged</h2>
<p>{link("https://www.clearerthinking.org/post/what-20-000-people-taught-us-about-entrepreneurship-and-startups", "What 20,000 People Taught Us About Entrepreneurship and Startups")} is <b>{escape(M['coverage'] or '')}</b>. Google's last crawl was {escape((M['last_crawl'] or '')[:10])}, the day of Markus's email, which fits an indexing request made that afternoon rather than anything the later fixes did. Search Console now lists these as the pages Google found it through: {refs}.</p>
<p>In 2026 before the email it had {M['before_email_2026']['impressions']:,} impressions and {M['before_email_2026']['clicks']} clicks. Since the email: {M['since_email']['impressions']:,} impressions and {M['since_email']['clicks']} clicks ({M['last_28_days']['impressions']:,} and {M['last_28_days']['clicks']} in the last 28 days, to {M['last_day_in_data']}). Beyond the hub, {len(M['other_pages_linking_to_it'])} other article{'s' if len(M['other_pages_linking_to_it']) != 1 else ''} link to it.</p>
<details><summary>Queries it has appeared for since October</summary><table><thead><tr><th>Query</th><th class='num'>Impressions</th><th class='num'>Clicks</th><th class='num'>Avg. position</th></tr></thead><tbody>{q}</tbody></table></details>""")

    cov_rows = sorted(I["coverage"].items(), key=lambda kv: -kv[1])
    trans = "".join(f"<tr><td>{escape(t['then'])}</td><td>{escape(t['now'])}</td><td class='num'>{t['n']}</td></tr>" for t in B["transitions"])
    wk = S["weekly"]
    events = [("2026-08-31", "Sitemaps resubmitted"), ("2026-09-28", "Hub live")]
    body.append(f"""
<h2>Is Google indexing the blog now?</h2>
<div class="card"><h3>Index status of all {I['articles']} articles</h3><p class="cap">Search Console URL Inspection, every article in the blog sitemap, {d['generated'][:10]}</p>
{charts.segmented_bar(coverage_parts(I['coverage']), I['articles'])}
{charts.data_table(["Google's verdict", "Articles"], [[k, n] for k, n in cov_rows], "Table view: every verdict")}</div>
<p>The comparison point is the August tracking sheet, which listed {B['posts']} blog posts Google was not indexing. Re-inspected today, <b>{B['posts_now_indexed']} of those {B['posts']} are indexed</b>. Of those {B['posts_now_indexed']}, {bt['first_impressions'].get('before the hub', 0)} were already showing up in search before the hub went live on {d['hub_live']}, {bt['first_impressions'].get('after the hub', 0)} first appeared after it, and {bt['first_impressions'].get('never seen in search', 0)} are indexed but have never earned an impression. So the hub can only be credited with the posts that surfaced after it, and even those would partly have happened anyway.</p>
<p>What points at the hub doing real work: Google names it as a referring page for {I['hub_is_referring_url']} articles, and {I['crawled_since_hub']} of {I['articles']} articles have been crawled since it went live ({I['never_crawled']} have still never been crawled).</p>
<div class="card"><h3>August's not-indexed posts that appeared in Google search, per week</h3><p class="cap">Of the {B['posts']} posts on the August list, how many earned at least one search impression each week (a page must be indexed to earn one)</p>
{charts.line_chart([(r['week'], r['baseline_posts_with_impressions']) for r in wk], "posts with impressions", events, "c1")}
{charts.data_table(["Week of", "August-list posts with impressions", "Their impressions", "Their clicks", "All blog pages with impressions", "All blog clicks"], [[r['week'], r['baseline_posts_with_impressions'], r['baseline_impressions'], r['baseline_clicks'], r['pages_with_impressions'], r['clicks']] for r in wk], "Table view: weekly numbers")}</div>
<div class="card"><h3>All blog pages that appeared in Google search, per week</h3><p class="cap">Distinct /post/ URLs with at least one impression, same weeks</p>
{charts.line_chart([(r['week'], r['pages_with_impressions']) for r in wk], "blog pages with impressions", events, "c2")}</div>
<p class="small">Six weeks before the hub ({before['weeks'][0]} to {before['weeks'][1]}) against the latest six ({latest['weeks'][0]} to {latest['weeks'][1]}): August-list posts seen in search went from {before['avg_baseline_posts_with_impressions']} to {latest['avg_baseline_posts_with_impressions']} a week, their clicks from {before['avg_baseline_clicks']} to {latest['avg_baseline_clicks']} a week. All blog pages seen in search: {before['avg_pages_with_impressions']:.0f} to {latest['avg_pages_with_impressions']:.0f}; all blog clicks: {before['avg_clicks']:.0f} to {latest['avg_clicks']:.0f} a week. This is a before and after with no control group, so read it as direction, not proof.</p>
<details><summary>Where each of the {B['posts']} August posts stands now</summary><table><thead><tr><th>Google's reason in August</th><th>Today</th><th class='num'>Posts</th></tr></thead><tbody>{trans}</tbody></table></details>""")
    return "".join(body)


def details(d: dict) -> str:
    L, C, T, I = d["links"], d["categories"], d["tools"], d["index"]
    dup = [p for p in d["duplicates"]["numbered_pairs"] if p["same_title"]]
    hub_only = L["buckets"].get("hub_only", 0)
    dup_rows = "".join(
        f"<tr><td>{escape(p['base']['title'] or '')}</td><td>{link(p['base']['url'], '/' + slug(p['base']['url'])[-28:])}<br><span class='small'>{escape(p['base']['coverage'] or '')}</span></td>"
        f"<td>{link(p['copy']['url'], 'the -1 copy')}<br><span class='small'>{escape(p['copy']['coverage'] or '')}</span></td></tr>" for p in dup)
    not_idx = "".join(f"<li>{link(r['url'])} <span class='small'>({escape(r['coverage'] or 'unknown')})</span></li>" for r in I["not_indexed"])
    missing = "".join(f"<li>{link(r['url'])} <span class='small'>({escape(r['coverage'] or 'unknown')})</span></li>" for r in I["wix_posts_missing_from_sitemap"])
    feed_rows = "".join(f"<tr><td>{escape(k)}</td><td class='num'>{v['status']}</td><td class='num'>{v['post_links_excl_chrome']}</td><td>{', '.join(x.replace('https://www.clearerthinking.org', '') for x in v['pagination_links']) or 'none'}</td></tr>"
                        for k, v in sorted(L["blog_feed"].items(), key=lambda kv: (len(kv[0]), kv[0])))
    cats = ", ".join(f"{k} {v}" for k, v in C["per_category"].items())
    return f"""
<h2>What is still open</h2>
<ul>
<li><b>The {len(dup)} duplicate glossary posts.</b> The only one of Markus's findings with a clean fix left undone: unpublish each <code>-1</code> copy and 301 it to the original (the Wix redirect API already used for the tools does this). About half an hour, and it removes the one place where the site sends Google two identical pages.</li>
<li><b>{hub_only} articles have the hub as their only internal link.</b> One link from a page that links to {L['hub']['links_in_raw_html']} others tells Google the article exists, not that it matters. The lever that remains is links from inside articles: a "related articles" block on new posts, and going back to add two or three contextual links into the older pieces worth ranking. Only {L['linked_from_another_post']} of {L['articles']} articles are linked from another article today.</li>
<li><b>{I['articles'] - I['indexed']} articles are not indexed</b>, {I['bias_series_not_indexed']} of them from the "Definition, Examples and Effects" glossary. That series reads to Google as thin and near-identical, so no amount of linking will fix it: improve the few with search demand, redirect or drop the rest.</li>
<li><b>Categories:</b> leave them. Assigning categories to {C['without_category']} posts by hand would add at most 20 crawlable links per category page, which the hub already provides for every post. Worth doing only if you want category pages for readers.</li>
<li><b>The <code>/tools/</code> dynamic page</b> still exists in Wix, so the sitemap keeps listing {T['in_sitemap']} <code>/tools/</code> URLs that redirect. Harmless, but deleting the dynamic item page stops new tools from spawning new duplicates.</li>
</ul>

<h2>The findings in detail</h2>
<h3>1 and 4. The blog archive</h3>
<p>Fetched as Googlebot today, <code>/blog</code> still exposes only the three newest articles and no link to any other archive page; <code>/blog/page/2</code> to <code>/blog/page/100</code> still work but nothing links to them. This is the Wix feed widget, which draws the list in the browser, and a Wix Editor site has no setting that changes it. The hub is the workaround: a normal blog post whose body Wix does render on the server, synced with the sitemap every Monday by <code>wix-hub-sync.yml</code> (last seven scheduled runs green; it lists {L['hub']['links_in_raw_html']} articles, {len(L['hub']['missing'])} missing, {len(L['hub']['stale'])} stale). Google has it: {escape(I['hub_status'].get('coverageState') or '')}, last crawled {escape((I['hub_status'].get('lastCrawlTime') or '')[:10])}.</p>
<details><summary>What each archive page exposes to a crawler</summary><table><thead><tr><th>Page</th><th class='num'>HTTP</th><th class='num'>Article links in raw HTML</th><th>Links to other archive pages</th></tr></thead><tbody>{feed_rows}</tbody></table></details>
<h3>2. Categories</h3>
<p>The Wix blog has four categories ({cats}) and {C['without_category']} of {C['posts']} published posts sit in none, the same {C['pct_without']}% Markus reported. His article has no category either. The research category page shows why this was deprioritised: with 25 posts assigned, its raw HTML links to {L['category_pages'].get('research', 0)}.</p>
<h3>3. Internal links</h3>
<p>Counting only real <code>&lt;a href&gt;</code> links in raw HTML across all {L['pages_crawled']} pages crawled, and ignoring links that appear on more than half of all pages (the menu and the "recent posts" strip, which always shows the three newest articles): {L['buckets'].get('other_pages', 0)} articles are linked from at least one other article or page, {L['buckets'].get('sitewide', 0)} are the three newest (linked from everywhere), and {hub_only} have the hub and nothing else. That last number is the like-for-like successor to Markus's {d['markus_claims']['zero_inbound']}: the hub turned "no link" into "one link" for all of them, and otherwise the picture is the same as in July.</p>
<h3>5. The /tools/ pages</h3>
<p>Each <code>/tools/&lt;slug&gt;</code> page was a 55-word wrapper around a link to the real tool on programs.clearerthinking.org, and the real tools already rank. So they were redirected on {d['hub_live']}, not linked. Checked one by one today: {", ".join(f"{n} return {k}" for k, n in sorted(T['by_status'].items()))}. The ones still answering 200 are the slugs with punctuation that the Wix redirect API cannot match, plus one that points at a third-party page by design.</p>
<h3>6. Duplicates</h3>
<div class='scroll'><table><thead><tr><th>Title</th><th>Original</th><th>Copy</th></tr></thead><tbody>{dup_rows}</tbody></table></div>

<h2>How this was checked</h2>
<ul class="small">
<li>Site: every URL in the blog, pages, categories and studies sitemaps ({L['pages_crawled']} pages) fetched today with a Googlebot user agent, raw HTML only, nothing rendered.</li>
<li>Categories: the Wix Blog API, all {C['posts']} published posts.</li>
<li>Index status: Search Console URL Inspection API for each article ({I['errors']} errors), property sc-domain:clearerthinking.org. Weekly figures: Search Analytics, web search, complete weeks from June 1.</li>
<li>July figures are quoted from Markus's email and were not recomputed. His crawl and this one may count "internal link" slightly differently.</li>
<li>Cross-checks: the hub's link count read two ways (rendered page and Wix API) agrees; no article that Search Console calls "not indexed" earned impressions in the last four weeks beyond what a recent status change explains (see the session notes).</li>
</ul>
<details><summary>The {I['articles'] - I['indexed']} articles Google is not indexing today</summary><ul class="urls">{not_idx}</ul></details>
<details><summary>{len(I['wix_posts_missing_from_sitemap'])} published posts that are not in the sitemap</summary><ul class="urls">{missing}</ul></details>
"""


if __name__ == "__main__":
    data = json.loads((HERE / "datapoints.json").read_text())
    html = page.render("Blog discoverability: where Markus's findings stand",
                       f"{timestamp()} · Markus's email of {data['email_date']} re-tested against the live site, the Wix blog and Search Console",
                       build(data) + details(data))
    OUT.write_text(html)
    print(f"wrote {OUT}")
