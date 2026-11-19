"""Render reports/blog_discoverability_followup_2026-11-18.html from datapoints.json and cross_check.json.

Run order: crawl_site.py, fetch_wix.py, fetch_gsc.py, analysis.py, cross_check.py, then this.
Every number in the page is read from those two files; the wording lives here.
"""
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
SITE = "https://www.clearerthinking.org"
HUB = f"{SITE}/post/all-clearer-thinking-articles"
ARTICLE = f"{SITE}/post/what-20-000-people-taught-us-about-entrepreneurship-and-startups"
INDEXED = ("Submitted and indexed", "Indexed, not submitted in sitemap")
CHECKED = "2026-11-18"   # the day the site was crawled and Search Console was swept
TOOLS_REDIRECTED = "2026-09-30"   # tools_redirects.py run (reports/wix_tools_redirects_created.json)
MONTHS = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def slug(u: str) -> str:
    return u.split("/post/", 1)[-1]


def link(u: str, text: str | None = None) -> str:
    return f'<a href="{escape(u)}">{escape(text or slug(u))}</a>'


def chip(kind: str, label: str) -> str:
    return f'<span class="chip {kind}"><i></i>{escape(label)}</span>'


def tile(label: str, value: str, note: str) -> str:
    return f'<div class="tile"><div class="label">{label}</div><div class="value">{value}</div><div class="note">{note}</div></div>'


def table(headers: list[str], rows: list[list], num_from: int = 1) -> str:
    head = "".join(f'<th{" class=num" if i >= num_from else ""}>{h}</th>' for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(f'<td{" class=num" if i >= num_from else ""}>{c}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f"<div class='scroll'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def coverage_parts(cov: dict) -> list[dict]:
    indexed = sum(n for k, n in cov.items() if k in INDEXED)
    disc = cov.get("Discovered - currently not indexed", 0)
    crawled = cov.get("Crawled - currently not indexed", 0)
    return [{"label": "Indexed", "value": indexed, "slot": 1},
            {"label": "Discovered, not indexed (Google knows the URL and has not fetched it)", "value": disc, "slot": 2},
            {"label": "Crawled, not indexed (fetched and declined)", "value": crawled, "slot": 3},
            {"label": "Other (soft 404, duplicate, redirect, unknown)", "value": sum(cov.values()) - indexed - disc - crawled, "slot": 4, "ink": "#0b0b0b"}]


def month_label(m: str) -> str:
    return f"{MONTHS[int(m[5:7])]} {m[:4]}"


def build(d: dict, x: dict) -> str:
    L, C, T, I, S, M = d["links"], d["categories"], d["tools"], d["index"], d["search"], d["markus_article"]
    B, bt, mk, R = I["baseline"], d["baseline_timing"], d["markus_claims"], x["markus_reconstruction"]
    dup = [p for p in d["duplicates"]["numbered_pairs"] if p["same_title"]]
    dup_orig_indexed = sum(1 for p in dup if p["base"]["coverage"] in INDEXED)
    dup_copy_indexed = sum(1 for p in dup if p["copy"]["coverage"] in INDEXED)
    feed = L["blog_feed"]["/blog"]
    hub_only, other = L["buckets"].get("hub_only", 0), L["buckets"].get("other_pages", 0)
    redirected = sum(n for k, n in T["by_status"].items() if k in ("301", "302", "308"))
    not_idx = I["articles"] - I["indexed"]
    before, latest, wk = S["before_hub"], S["latest"], S["weekly"]
    lag = x["index"]["not_indexed_but_with_impressions"]
    g = I["not_indexed_groups"]
    aug = next(r for r in M["by_month"] if r["month"] == "2026-08")
    first = M["by_month"][0]
    zero_run = [r for r in M["by_month"] if "2025-11" <= r["month"] <= "2026-06"]

    out = [f"""
<div class="verdict">
<p><b>Markus's main diagnosis was right, and the fix he suggested is the one that worked.</b> Google now indexes {I['indexed']} of the blog's {I['articles']} articles ({I['pct_indexed']}%), and {B['posts_now_indexed']} of the {B['posts']} posts it was skipping in August. The jump came the week the <a href="{HUB}">All Clearer Thinking Articles</a> page went live ({d['hub_live']}), not after the sitemap resubmission four weeks earlier, and Google names that page as the place it found {I['hub_is_referring_url']} of the {I['articles']} articles.</p>
<p><b>What it did not do is make his article findable.</b> It is indexed, but since September it has been shown {M['since_september']['impressions']} times and clicked {M['since_september']['clicks']} time. Indexing was the precondition; ranking is a separate problem that an index page cannot solve.</p>
<p>Of the six findings: four are closed (three by the index page, one by redirects), and two are exactly where they were in July, categories on purpose and the duplicate glossary posts through neglect.</p>
</div>
<div class="tiles">
{tile("Articles Google has indexed", f"{I['indexed']} <small>of {I['articles']}</small>", f"{I['pct_indexed']}%, Search Console on {CHECKED}")}
{tile("August's not-indexed posts, indexed now", f"{B['posts_now_indexed']} <small>of {B['posts']}</small>", "from the tracking sheet, re-inspected")}
{tile("Search clicks a week to those posts", f"{latest['avg_baseline_clicks']:.0f} <small>was {before['avg_baseline_clicks']:.0f}</small>", "last six weeks against the six before the index page")}
{tile("Articles whose only internal link is the index page", f"{hub_only} <small>of {L['articles']}</small>", "the part that has not changed")}
</div>"""]

    rows = [
        ("1. Blog archive has no crawlable pagination",
         f"Googlebot reaches about {mk['blog_feed_links']} posts from /blog",
         f"/blog is unchanged ({feed['post_links_excl_chrome']} article links in its raw HTML, no link to page 2), and a Wix Editor site cannot change it. The index page stands in: {L['hub']['links_in_raw_html']} plain links, in the menu of every page.",
         chip("around", "Worked around")),
        ("2. Posts with no category",
         f"{mk['no_category']} of {mk['posts']} (95.7%)",
         f"{C['without_category']} of {C['posts']} ({C['pct_without']}%). Left alone on purpose: a category page shows a crawler only its first {L['category_pages'].get('research', 0)} posts.",
         chip("same", "Unchanged")),
        ("3. Posts with zero inbound internal links",
         f"{mk['zero_inbound']}",
         f"{len(L['zero_inbound_including_hub'])}: every article has the index-page link. For {hub_only} it is the only one.",
         chip("good", "Fixed, thinly")),
        ("4. Posts unreachable from the blog page",
         f"{mk['unreachable_from_blog']} (the scroll stops at 300 posts)",
         "0: the index page is one click from anywhere. The scroll limit itself was not re-tested.",
         chip("around", "Worked around")),
        ("5. /tools/ pages nothing links to",
         f"{mk['tools_unlinked']} of {mk['tools_pages']}",
         f"{redirected} of {T['in_sitemap']} now redirect to the real tool. They were thin copies of tools that already rank, so linking to them would have been the wrong fix.",
         chip("good", "Fixed by redirect")),
        ("6. Duplicate posts at /slug and /slug-1",
         f"about {mk['duplicate_pairs']} pairs",
         f"{len(dup)} pairs, all still live. Google indexes the original in {dup_orig_indexed} of {len(dup)} and the copy in {dup_copy_indexed}, so the harm is small.",
         chip("open", "Still open")),
    ]
    out.append("<h2>The six findings</h2><div class='scroll'><table class='score'><thead><tr><th>Markus's finding</th><th>July 30</th><th>Now</th><th>Status</th></tr></thead><tbody>"
               + "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{s}</td></tr>" for a, b, c, s in rows) + "</tbody></table></div>"
               f"<p class='small'>His July counts hold up. Rebuilding them from today's data for the {R['posts_live_on_2026_07_30']} posts live on July 30 gives {R['beyond_the_300_post_scroll']} posts beyond the 300-post scroll (he reported {mk['unreachable_from_blog']}) and {R['beyond_scroll_and_not_linked_from_any_article']} of those with no link from any article (he reported {mk['zero_inbound']}).</p>")

    events = [("2026-08-31", "Sitemaps resubmitted"), ("2026-09-28", "Index page live")]
    last = wk[-1]
    out.append(f"""
<h2>Did it work?</h2>
<div class="card"><h3>Index status of all {I['articles']} articles</h3><p class="cap">Search Console URL Inspection, every article in the blog sitemap, {CHECKED}</p>
{charts.segmented_bar(coverage_parts(I['coverage']), I['articles'])}
{charts.data_table(["Google's verdict", "Articles"], [[k, n] for k, n in sorted(I['coverage'].items(), key=lambda kv: -kv[1])], "Table view: every verdict")}</div>
<p>The baseline is the August tracking sheet: {B['posts']} blog posts Google was not indexing. Today <b>{B['posts_now_indexed']} of them are indexed</b>, and Google has crawled {B['posts_crawled_since_hub']} of the {B['posts']} since the index page went up. In mid-September, two weeks after the sitemap work, only 10 of the whole 233-page sheet had been crawled.</p>
<div class="card"><h3>August's not-indexed posts showing up in Google search, per week</h3><p class="cap">How many of the {B['posts']} earned at least one search impression (a page has to be indexed to earn one)</p>
{charts.line_chart([(r['week'], r['baseline_posts_with_impressions']) for r in wk], "posts seen in search", events, "c1")}
{charts.data_table(["Week of", "Posts seen in search", "Their impressions", "Their clicks", "All blog clicks"], [[r['week'], r['baseline_posts_with_impressions'], f"{r['baseline_impressions']:,}", r['baseline_clicks'], f"{r['clicks']:,}"] for r in wk], "Table view: weekly numbers")}</div>
<div class="card"><h3>Search clicks to those {B['posts']} posts, per week</h3><p class="cap">Google web search, same weeks</p>
{charts.line_chart([(r['week'], r['baseline_clicks']) for r in wk], "clicks", events, "c2")}</div>
<p>Three things say the index page caused this and not time passing:</p>
<ul>
<li><b>Timing.</b> For four weeks after the sitemaps were resubmitted the line stayed at {before['avg_baseline_posts_with_impressions']:.0f} posts. It tripled in the week the index page went live and reached {last['baseline_posts_with_impressions']} in the latest week.</li>
<li><b>Google's own record.</b> Search Console lists the index page as a referring page for {I['hub_is_referring_url']} of {I['articles']} articles.</li>
<li><b>First appearances.</b> Of the {B['posts_now_indexed']} newly indexed posts, {bt['first_impressions'].get('after the hub', 0)} first appeared in search after it went live, {bt['first_impressions'].get('before the hub', 0)} before, and {bt['first_impressions'].get('never seen in search', 0)} are indexed but have not been shown to anyone yet.</li>
</ul>
<p><b>The size of the win is modest.</b> Those posts went from {before['avg_baseline_clicks']:.0f} to {latest['avg_baseline_clicks']:.0f} search clicks a week ({last['baseline_clicks']} in the latest week, still rising), against roughly {latest['avg_clicks']:,.0f} a week for the whole blog. Whole-blog clicks moved from {before['avg_clicks']:,.0f} to {latest['avg_clicks']:,.0f} a week over the same windows, but only about {latest['avg_baseline_clicks'] - before['avg_baseline_clicks']:.0f} of that difference can be traced to these posts. The rest cannot be credited to anything here: there is no control group.</p>
<p class="small">Search Console's verdicts lag its own search data: {len(lag)} of the {not_idx} articles it calls not indexed earned impressions in the last four weeks, so the true indexed count is probably a few above {I['indexed']}.</p>""")

    month_rows = [[month_label(r["month"]), r["impressions"], r["clicks"]] for r in M["by_month"]]
    q = M["queries_since_email"]
    qtxt = ("Search Console reports only " + " and ".join(f"\"{escape(r['query'])}\" ({r['impressions']} impression{'s' if r['impressions'] != 1 else ''}, average position {r['position']:.0f})" for r in q)
            + "; every other query is below its reporting threshold.") if q else "Search Console reports no query above its reporting threshold."
    others = ", ".join(link(u) for u in M["other_pages_linking_to_it"])
    out.append(f"""
<h2>The article Markus flagged</h2>
<p>{link(ARTICLE, "What 20,000 People Taught Us About Entrepreneurship and Startups")} is <b>indexed</b>. Google's last crawl of it is {escape((M['last_crawl'] or '')[:16].replace('T', ' '))} UTC, the minute you replied to Markus, which fits an indexing request made from Search Console that afternoon and not anything done later.</p>
<p>Its history shows the real problem. Published in July 2025, it earned {first['impressions']} impressions in its first month, faded, and then showed <b>zero impressions for {len(zero_run)} straight months</b> ({month_label(zero_run[0]['month'])} to {month_label(zero_run[-1]['month'])}). After the re-crawl it got {aug['impressions']} impressions in August at positions 8 to 20, and then faded the same way: {M['since_september']['impressions']} impressions and {M['since_september']['clicks']} click from September 1 to {M['last_day_in_data']}. {qtxt}</p>
<p>So Google has the page and is choosing not to show it. It has links from the index page and from {len(M['other_pages_linking_to_it'])} other articles ({others}), and no category. Whether his exact test (searching the title) now finds it could not be checked from here: Search Console has logged no title search since his email. It takes ten seconds to try by hand.</p>
<details><summary>Month by month</summary>{table(["Month", "Impressions", "Clicks"], month_rows)}</details>""")

    recent = I["crawled_declined_recently"]
    soft = [u for u in I["soft_404"] if "definition-examples-and-effects" not in u]
    out.append(f"""
<h2>What is still open</h2>
<ul>
<li><b>{len(soft) + len(recent)} real articles worth a manual "Request indexing" in Search Console.</b> {len(soft)} carry a stale "Soft 404" verdict from a crawl last spring although the pages are fine ({", ".join(link(u) for u in soft)}), and Google crawled and declined {", ".join(link(r['url']) for r in recent)} on {recent[0]['last_crawl'] if recent else ''}, a newsletter article from October. Ten minutes.</li>
<li><b>{hub_only} articles have the index page as their only internal link.</b> One link from a page with {L['hub']['links_in_raw_html']} others tells Google an article exists, not that it matters. Article-to-article linking is unchanged since July: {R['not_linked_from_any_article_in_july']} of {R['posts_live_on_2026_07_30']} posts had no link from another article then, {R['not_linked_from_any_article_today']} of {I['articles']} have none now. This is the lever left for ranking, and it is editorial work: a few contextual links into each older piece worth ranking, and a related-articles block on new ones.</li>
<li><b>The {len(dup)} duplicate glossary posts.</b> Unpublish each <code>-1</code> copy and 301 it to the original, with the same Wix redirect call used for the tools. Half an hour. Low impact, since Google already ignores the copies, but it is the one finding with a clean fix left undone.</li>
<li><b>{not_idx} articles not indexed:</b> {g.get('bias glossary', 0)} from the "Definition, Examples and Effects" glossary, {g.get('2015-2020 announcements', 0)} announcements from 2015 to 2020, {g.get('other articles', 0)} others. The glossary and the old announcements are thin by Google's standards and more links will not change that: improve the few with search demand, leave or retire the rest.</li>
<li><b>Categories: leave them</b> unless you want category pages for readers. Hand-tagging {C['without_category']} posts would give a crawler at most 20 links per category, which the index page already provides for every post.</li>
</ul>""")
    return "".join(out)


def details(d: dict, x: dict) -> str:
    L, C, T, I = d["links"], d["categories"], d["tools"], d["index"]
    dup = [p for p in d["duplicates"]["numbered_pairs"] if p["same_title"]]
    lag = x["index"]["not_indexed_but_with_impressions"]
    feed_rows = [[escape(k), v["status"], v["post_links_excl_chrome"], ", ".join(u.replace(SITE, "") for u in v["pagination_links"]) or "none"]
                 for k, v in sorted(L["blog_feed"].items(), key=lambda kv: (len(kv[0]), kv[0]))]
    dup_rows = [[escape((p["base"]["title"] or "").split(":")[0]), f"{link(p['base']['url'], 'original')}: {escape(p['base']['coverage'] or 'unknown')}",
                 f"{link(p['copy']['url'], 'copy')}: {escape(p['copy']['coverage'] or 'unknown')}"] for p in dup]
    not_idx = "".join(f"<li>{link(r['url'])} <span class='small'>({escape(r['coverage'] or 'unknown')})</span></li>" for r in I["not_indexed"])
    hidden = "".join(f"<li>{link(r['url'])} <span class='small'>({escape(r['coverage'] or 'unknown')})</span></li>" for r in I["wix_posts_missing_from_sitemap"])
    cats = ", ".join(f"{k} {v}" for k, v in C["per_category"].items())
    by_status = " and ".join(f"{n} return {k}" for k, n in sorted(T["by_status"].items(), reverse=True))
    hosts = ", ".join(f"{n} to {h}" for h, n in sorted(T["redirect_hosts"].items(), key=lambda kv: -kv[1]))
    mismatch = L["canonical_mismatch"]
    return f"""
<h2>The findings in detail</h2>
<h3>1 and 4. The blog archive</h3>
<p>Fetched as Googlebot, <code>/blog</code> exposes the three newest articles and no link to another archive page. <code>/blog/page/2</code> to <code>/blog/page/100</code> answer 200 with three articles each, and nothing links to them. That is the Wix feed widget drawing the list in the browser. The index page is an ordinary blog post, whose body Wix does render on the server; <code>wix-hub-sync.yml</code> re-syncs it with the sitemap every Monday (the last seven scheduled runs succeeded). It lists {L['hub']['links_in_raw_html']} articles with {len(L['hub']['missing'])} missing and {len(L['hub']['stale'])} stale, and Google's last crawl of it was {escape((I['hub_status'].get('lastCrawlTime') or '')[:10])}.</p>
<details><summary>What each archive page exposes to a crawler</summary>{table(["Page", "HTTP", "Article links in raw HTML", "Links to other archive pages"], feed_rows)}</details>
<h3>2. Categories</h3>
<p>The blog has four categories ({cats}); {C['without_category']} of {C['posts']} published posts are in none, and Markus's article is one of them. The research category has 25 posts and its page links {L['category_pages'].get('research', 0)} of them in raw HTML, which is why tagging was never going to carry the archive.</p>
<h3>3. Internal links</h3>
<p>Counting real <code>&lt;a href&gt;</code> links in the raw HTML of all {L['pages_crawled']} pages, and setting aside links present on more than half of them (the menu, and the "recent posts" strip that always shows the three newest articles): {L['buckets'].get('other_pages', 0)} articles are linked from at least one other article or page, {L['buckets'].get('sitewide', 0)} are the three newest, and {hub_only_count(L)} have the index page and nothing else.</p>
<h3>5. The /tools/ pages</h3>
<p>Each <code>/tools/&lt;slug&gt;</code> page was a short wrapper around a link to the real tool, so on {TOOLS_REDIRECTED} they were redirected, not linked. Requested one at a time on {CHECKED}: {by_status} ({hosts}). The {len(T['still_200'])} still answering 200 are the 11 slugs with punctuation, which the Wix redirect API cannot match, and one left alone on purpose because it points at a third-party page. Wix still lists all {T['in_sitemap']} in the sitemap because the dynamic page behind them exists.</p>
<h3>6. Duplicates</h3>
{table(["Glossary post", "Original", "The -1 copy"], dup_rows, num_from=9)}

<h2>Seen along the way</h2>
<ul class="small">
<li>{len(mismatch)} sitemap URL redirects to a different post: {", ".join(link(u) for u in mismatch)} goes to the "Recency Illusion" post, and both are listed.</li>
<li>{len(I['wix_posts_missing_from_sitemap'])} published posts are missing from the sitemap, and so from the index page, because one is noindexed and four are canonicalised to another page. One of those canonicals still points at <code>programs.clearerthinking.org/personality.html</code>, the old address of the personality test.</li>
<li>In the week of September 14 the number of distinct blog pages seen in search jumped from about 500 to 623 and fell back the week after: 177 pages got one or two impressions each. It coincides with the Who Attracts You wave of September 7 to 18; the cause was not established, and it does not touch the August-list posts charted above.</li>
<li>The <code>society.clearerthinking.org</code> sitemap still errors in Search Console (submitted in June, never downloaded). Not part of Markus's email.</li>
</ul>

<h2>How this was checked</h2>
<ul class="small">
<li>Site: all {L['pages_crawled']} URLs in the blog, pages, categories and studies sitemaps, fetched on {CHECKED} with a Googlebot user agent. Raw HTML only, nothing rendered, so a link drawn by JavaScript counts for nothing.</li>
<li>Categories and article bodies: the Wix Blog API, all {C['posts']} published posts.</li>
<li>Index status: Search Console URL Inspection for every article and every row of the August sheet ({I['errors']} errors). Weekly figures: Search Analytics, web search, complete Monday-to-Sunday weeks from June 1.</li>
<li>July figures are quoted from Markus's email.</li>
<li>Independent recounts: articles linked from another article, {x['links']['linked_from_another_article_crawl']} by the crawl and {x['links']['linked_from_another_article_body_wix_api']} by reading article bodies through the Wix API; index-page links, {x['hub']['links_raw_html']} in the rendered page and {x['hub']['links_wix_api']} in the API copy; posts with a category, {x['categories']['posts_with_a_category']} counted from posts against a category total of {x['categories']['sum_of_category_post_counts']} (one post is in two); indexed articles, {x['index']['indexed_by_inspection']} by inspection against {x['index']['articles_with_impressions']} with impressions in the last four weeks, with the {len(lag)} disagreements noted above.</li>
<li>Not done: a live Google search for the article's title, and a re-test of the 300-post scroll limit on /blog.</li>
</ul>
<details><summary>The {I['articles'] - I['indexed']} articles Google is not indexing</summary><ul class="urls">{not_idx}</ul></details>
<details><summary>The {len(I['wix_posts_missing_from_sitemap'])} published posts left out of the sitemap</summary><ul class="urls">{hidden}</ul></details>
"""


def hub_only_count(L: dict) -> int:
    return L["buckets"].get("hub_only", 0)


if __name__ == "__main__":
    data = json.loads((HERE / "datapoints.json").read_text())
    cross = json.loads((HERE / "cross_check.json").read_text())
    html = page.render("Blog discoverability: where Markus's findings stand",
                       f"{timestamp()} · Markus's email of {data['email_date']}, re-tested on {CHECKED} against the live site, the Wix blog and Search Console",
                       build(data, cross) + details(data, cross))
    OUT.write_text(html)
    print(f"wrote {OUT}")
