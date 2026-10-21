"""Build reports/upt_ranking_plan_2026-10-21.html from datapoints.json (GSC weekly/monthly series).

Run:  .venv/bin/python reports/upt_ranking_plan_2026-10-21_src/build_report.py
The SERP table, timeline and recommendations are written here as content; the charts read datapoints.json
(produced by the GSC pull in the same session, see the docstring in the report's method section).
"""
import json
from datetime import datetime
from pathlib import Path

SRC = Path(__file__).parent
OUT = SRC.parent / "upt_ranking_plan_2026-10-21.html"
data = json.loads((SRC / "datapoints.json").read_text())
stamp = datetime.now().strftime("%Y-%m-%d %I:%M%p").lower()

SERP = [
    (1, "16personalities.com/free-personality-test", 86, 19, "5,547", "organic #1"),
    ("2", "AI Overview (10 cited sources, the UPT is one of them)", "", "", "", "SERP feature"),
    ("3", "People also ask (4 questions)", "", "", "", "SERP feature"),
    (4, "seemypersonality.com (homepage, questions on the page)", 37, 9, "918", "organic"),
    (5, "my-personality-test.com (homepage)", 46, 12, "1,155", "organic"),
    (6, "truity.com TypeFinder (106 questions on the page)", 77, 23, "931", "organic"),
    (7, "programs.clearerthinking.org/personality-test.html (UPT)", 63, 5, "126", "organic, test loads only after a click"),
    (8, "personalityjunkie.com free test", 46, 4, "179", "organic"),
    (9, "humanmetrics.com/personality/test", 72, 15, "3,188", "organic"),
    (10, "mypersonality.net", 42, 22, "1,085", "organic"),
]

TIMELINE = [
    ("May 2026", "Best month in the window: 2,802 clicks, position 7.4 on both devices, desktop CTR 1.5%."),
    ("Late May to June", "CTR halves (desktop 1.5% to 0.5%, mobile 0.74% to 0.40% by Jun 20-30) and position slips about one spot. A core update reportedly ran May 21 to Jun 2; unconfirmed."),
    ("Jun 2 to 22", "A link-dump spam burst (pages titled 'TG @SEO_LINKK_ORDER', '@MASSLINKER') adds about 120 junk referring domains. Not bought by CT, not targeted at CT, nofollow, ignored by Google. No action."),
    ("Jul 21", "New intro page launches (3,000 words, hero, FAQ). Title changes from 'Free Scientific Personality Test: Briggs-Myers, Big 5 & More' to 'Ultimate Personality Test | ClearerThinking.org'. personality.html starts 301ing here. CTR did not fall after this (it rose slightly), so the title is not what cost the clicks."),
    ("Sep 23", "Igor's title and description fix is pushed as branch bugfix/2026-09-23/upt-seo-title-description in the team repo. No PR was opened; it is still unmerged on Oct 21."),
    ("Sep 24 to Oct 8", "Google's September 2026 spam update rolls out (the longest spam rollout of the year)."),
    ("Week of Sep 28", "Mobile impressions for 'personality test' fall 63% in one week (30,035 to 11,188) and stay there. Desktop is flat. Site-wide mobile is fine. The page did not change, loads in 1.8 s on mobile, and Google crawled it as mobile on Oct 21 with the right canonical."),
    ("Oct 4", "thebehavioralscientist.com's '14 online tests compared' adds a dofollow link to the UPT (DR 53), unprompted."),
    ("Oct 17", "Ahrefs records video thumbnails as a new feature on the 'personality test' SERP (absent on Sep 15)."),
]

RECS = [
    dict(score=8, name="Open the PR for the Sep 23 title fix today, with one tweak",
         what="The branch already changes the title to 'Free Personality Test: Myers-Briggs style, Big 5 & Enneagram' and reads title and description from program.yml. Open the PR to Josh now; the only tweak worth making is leading the description with the same words searchers type ('Free personality test ... 12 minutes, instant results').",
         lay="The blue headline Google shows for the page is the single biggest thing deciding whether a searcher clicks. The current one says 'Ultimate Personality Test'; the #1 result says 'Free Personality Test'.",
         pro="Ten minutes of work, already written and preview-tested on Sep 23. The current title spends its 60 characters on a brand word and the site name, which Google already truncates. Every top-6 competitor leads with 'Free' or the test name.",
         con="Be honest about the ceiling: the data shows the July title change did not cut CTR (CTR had already halved in June), so expect a CTR lift of maybe a third, not a ranking jump. Click-through is not a confirmed ranking signal.",
         owner="Igor (PR), Josh (merge). Measure: desktop CTR for the exact query, 28 days before vs after."),
    dict(score=8, name="Give the test a sitewide internal link from every programs.* tool page, and clean up the links that exist",
         what="Add one line to the shared program template (src/templates/program.liquid in the team repo): a footer or nav link 'Free personality test' to /personality-test.html. Then fix the links CT already has: the All Tools page links the OLD url with the anchor 'Start'; five personality blog posts and CT's own research PDF link the old url; three personality posts have no link at all; the UPT page itself links to no other CT page except the study.",
         lay="Google decides how important a page is partly by how many of your own pages point to it and with what words. Right now most of CT's own links point at a redirect, use words like 'Start', or do not exist.",
         pro="Entirely in CT's control, ships in days, and gives the page ~150 same-domain links with the exact anchor on a DR 63 domain. Google's URL Inspection lists just one internal page as a known referrer today. The three programs.* pages that got internal links in September were the ones that progressed in the index.",
         con="Internal links are a moderate signal on a head term, and Google must recrawl the linking pages before anything moves, so two weeks may show only the start of the effect.",
         owner="Igor (Wix anchors, blog links, PR for the template), Josh (merge). Measure: Google's referringUrls in URL Inspection, then position."),
    dict(score=7, name="Answer the 'People also ask' questions on the page, word for word",
         what="The SERP shows a PAA box right under the AI Overview on mobile. Rewrite the existing FAQ section so each H3 is one of the live questions ('Is there a truly free Myers-Briggs test?', 'What is the most reliable personality test?', 'What are the rarest personality types?', 'What's my Myers-Briggs type?', 'How do I know if I'm type A or B?') followed by a 40 to 60 word direct answer that names the test.",
         lay="Google fills the 'People also ask' box with short answers lifted from pages. Matching the question exactly is how a page gets picked, and a PAA slot is a second spot on page 1.",
         pro="Content edit only, no engineering. The page already has a 1,600 word explainer, so this is a rewrite of headings and first sentences, not new writing. A PAA slot sits above the organic result on mobile, which is exactly where the UPT lost visibility.",
         con="PAA ownership rotates and Google may prefer Psychology Today or 16personalities for the same answer. No guarantee, and GSC does not report PAA separately.",
         owner="Igor writes, Josh deploys (template.liquid). Measure: impressions for the question queries in GSC."),
    dict(score=7, name="Get into the pages that already rank for 'best', 'most accurate' and 'best free personality test'",
         what="Checked today: deepersignals.com's '7 popular personality tests for work' (#7 for 'best personality test'), Psychology Today's tests directory (#10 'best free'), thepersonalitylab.org (#8) and Wikipedia's 'Personality test' external links do not mention CT. The Reddit r/entp thread 'What's the most accurate personality test on the internet?' ranks #3 for both 'best' and 'most accurate'; r/careerguidance and two Quora questions rank for 'best free'. Pitch the editors with the Scientific American piece and the 300,000-person validation; have Spencer answer the threads under his own name with the affiliation stated.",
         lay="Articles that list the best tests already sit on page 1 for the comparison searches. Being named in them brings links Google counts, and readers who then search for the test by name.",
         pro="Fastest legitimate link source: thebehavioralscientist added CT on Oct 4 without being asked, and Spencer's own SciAm article ranks #7 for 'most accurate personality test'. Reddit answers can be live within a day.",
         con="Editor response rates run 5 to 10% and links land in 2 to 6 weeks. Reddit and Quora links are nofollow (visibility and brand searches, not link equity). Undisclosed self-promotion gets removed, so it must be transparent.",
         owner="Igor (outreach), Spencer (threads, 30 min). Measure: new referring domains in Ahrefs; brand query impressions in GSC."),
    dict(score=7, name="Start tracking the mobile SERP you cannot see",
         what="Ahrefs Rank Tracker (project 2733839) tracks 71 keywords and not 'personality test'. Add it for US desktop and US mobile today, plus 'free personality test' and 'personality type test'. Add a weekly GSC check of mobile vs desktop impressions for the exact query to the Friday letter.",
         lay="The page fell off mobile page 1 on Sep 28 and nobody noticed for three weeks because nothing watches it.",
         pro="Cheap, and the only way to tell within days whether anything below is working, and whether the mobile drop is a layout change or a real rank loss.",
         con="Measurement, not a lever. The Ahrefs API cannot add keywords, so it is a manual step in the Ahrefs UI.",
         owner="Igor, 15 minutes. Measure: n/a."),
    dict(score=6, name="Make the page look like a test to Google, not an article about tests",
         what="Googlebot never sees a single question: the GuidedTrack program loads only after a click. Ahrefs' classifier reads the page as an Article. The two pages ranking #4 and #6 with far weaker domains render their questions in the HTML (Truity, 106; SeeMyPersonality, 6). Render the first screen of questions (or at least the first three, as static HTML that hands off to GuidedTrack on the first answer) above the fold, and move the 1,600 word explainer below the test.",
         lay="Someone typing 'personality test' wants to start answering questions. Google tries to serve pages that do that; our page reads to it like an essay with a button.",
         pro="This is the only on-page change that could move ranking rather than clicks, and the SERP evidence (a DR 37 homepage at #4) says format matters here as much as authority.",
         con="Engineering in Josh's repo and in the GuidedTrack flow; the 'shouldShowIntroPage' handoff would need care so answers are not asked twice. Two weeks is tight and the effect is a judgment call, not a measurement.",
         owner="Josh, with Igor on the copy. Measure: Ahrefs page_type, then position."),
    dict(score=6, name="Ask the organisations that already link to CT to link to the test specifically",
         what="80,000 Hours links to it twice; GuidedTrack's own site, Spark Wave, the Alliance for Decision Education, Annie Duke, Positly and the MLA partners (Hive, Leaf, Non-Trivial) all have reasons to mention a free, research-backed personality test. One email each: a one-line description and the url. Also ask Scientific American and The Decision Lab to update their links from personality.html to personality-test.html (optional; the 301 passes most value).",
         lay="Friends of the organisation already link to CT in general. Asking them for a link to this one page is the cheapest link request there is.",
         pro="Warm contacts, high reply rate, and the links come from relevant DR 45 to 76 domains. Two weeks is enough for three to five of them.",
         con="A handful of links against a 5,547-domain gap at #1. Helps pass #4 to #6 over a quarter, not reach #1 in a fortnight.",
         owner="Igor and Spencer. Measure: referring domains to the exact url."),
    dict(score=5, name="Send the test to the full list with the compare-with-a-friend hook",
         what="A dedicated send (not a debrief mention) to the 93k list: 'Take the test, then send it to one person and see your personalities side by side'. The compare feature already exists (?compare=1).",
         lay="Brand searches and shares are the organic way a page earns links and demand. The list is the one audience CT can reach tomorrow.",
         pro="Zero cost, immediate sign-ups whatever happens to rankings, and it produces the 'clearer thinking personality test' searches and the social posts that earn natural links.",
         con="No evidence that brand demand moves a head-term ranking inside two weeks; the Positly click experiment showed clicks alone do nothing at this scale. Treat the ranking effect as a bonus.",
         owner="Igor, one send. Measure: beehiiv clicks, GSC brand queries."),
    dict(score=5, name="Mark up Spencer's video and retitle it for the query",
         what="The SERP gained video thumbnails in late September. The page embeds 'We Tested Every Personality Test. THIS One Works Best'. Add VideoObject structured data (name, description, thumbnail, uploadDate, duration, embedUrl) and retitle the YouTube upload to lead with 'Free Personality Test'.",
         lay="Google now shows little video pictures on this results page. A thumbnail next to our result makes it bigger and more clickable on a phone.",
         pro="One day of work; no risk; the page currently has no structured data at all.",
         con="Since 2023 Google only shows a video thumbnail when the video is the main content of the page, which this landing page is not. The YouTube video would have to rank on its own merits in the video module.",
         owner="Josh (markup), Igor (YouTube). Measure: 'Video' search appearance in GSC."),
    dict(score=5, name="Pitch CT's data as a story (worth 7 over a quarter, 5 inside two weeks)",
         what="'We tested every personality test against life outcomes' is already a Scientific American article (DR 91) and a Decision Lab link. A fresh angle (which test predicts income, relationships, or anxiety best, from the 300,000-person dataset) pitched to science and psychology desks, plus Spencer answering journalist requests on Qwoted or Featured.",
         lay="Reporters link to original data. CT has data nobody else has.",
         pro="The one link source that can close a gap of thousands of domains over time; it already worked once.",
         con="Two weeks is too short for most placements, and it needs Spencer's time, not Igor's.",
         owner="Spencer and Igor. Measure: referring domains over 90 days."),
]

DONTS = [
    "Do not disavow the June spam links. They are generic link-dump pages that link to thousands of sites; Google ignores them and a disavow file gains nothing. Revisit only if a manual action appears in Search Console.",
    "Do not buy placements (Good Men Project and the DR 70 to 79 lifestyle sites from the September research). A paid link during an active spam update window is the one thing that can make this worse.",
    "Do not rerun the Positly click experiment. 2,928 real clicks moved the ranking by zero; the 2026-09-23 report settles it.",
    "Do not touch the url, canonical or redirect. Google indexes the page correctly, crawled it as mobile on Oct 21, and the 301 from personality.html is clean.",
    "Do not read the 4.1M desktop impressions of Oct 2025 to Mar 2026 as lost traffic. That was a reporting artefact and this plan ignores that window.",
]

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

serp_rows = "".join(f"<tr><td>{esc(p)}</td><td>{esc(u)}</td><td>{esc(dr)}</td><td>{esc(ur)}</td><td>{esc(rd)}</td><td>{esc(k)}</td></tr>" for p,u,dr,ur,rd,k in SERP)
tl_rows = "".join(f"<tr><th scope='row'>{esc(d)}</th><td>{esc(t)}</td></tr>" for d,t in TIMELINE)
rec_html = ""
for i, r in enumerate(sorted(RECS, key=lambda x: -x["score"]), 1):
    rec_html += f"""
<article class="rec">
  <div class="rec-head"><span class="score">{r['score']}<small>/10</small></span><h3>{i}. {esc(r['name'])}</h3></div>
  <p>{esc(r['what'])}</p>
  <p class="lay"><strong>In plain terms:</strong> {esc(r['lay'])}</p>
  <div class="pc"><div><strong>Strongest case for</strong><p>{esc(r['pro'])}</p></div><div><strong>Strongest case against</strong><p>{esc(r['con'])}</p></div></div>
  <p class="owner">{esc(r['owner'])}</p>
</article>"""
dont_html = "".join(f"<li>{esc(d)}</li>" for d in DONTS)
weekly = data["weekly"]; monthly = data["monthly"]
wk_rows = ""
for w in sorted({x["week"] for x in weekly}):
    d = {x["device"]: x for x in weekly if x["week"] == w}
    dd, mm = d.get("DESKTOP", {}), d.get("MOBILE", {})
    wk_rows += f"<tr><td>{w}</td><td>{dd.get('impressions',0):,}</td><td>{mm.get('impressions',0):,}</td><td>{dd.get('clicks',0):,}</td><td>{mm.get('clicks',0):,}</td><td>{dd.get('position','')}</td><td>{mm.get('position','')}</td></tr>"

html = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UPT ranking plan</title>
<meta name="description" content="Why the Ultimate Personality Test sits at #7 for 'personality test', what happened on Sep 28, and the ranked two-week plan.">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--hair:#e1e0d9;--s1:#2a78d6;--s2:#eb6834;--ring:rgba(11,11,11,.10);--good:#006300;--crit:#d03b3b;--wash:#f0efec}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--hair:#2c2c2a;--s1:#3987e5;--s2:#d95926;--ring:rgba(255,255,255,.10);--good:#0ca30c;--crit:#e66767;--wash:#262624}}
:root[data-theme="dark"]{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--hair:#2c2c2a;--s1:#3987e5;--s2:#d95926;--ring:rgba(255,255,255,.10);--good:#0ca30c;--crit:#e66767;--wash:#262624}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:30px;line-height:1.2;margin:0 0 6px}
h2{font-size:21px;margin:44px 0 12px}
h3{font-size:17px;margin:0}
.sub{color:var(--ink2);margin:0 0 24px}
.verdict{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:20px 22px;margin:20px 0}
.verdict p{margin:8px 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 16px}
.tile .label{font-size:13px;color:var(--ink2)}
.tile .value{font-size:28px;font-weight:600;margin:2px 0}
.tile .delta{font-size:13px;color:var(--ink2)}
.delta.bad{color:var(--crit)}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:18px 18px 10px;margin:16px 0}
.card h3{font-size:16px;margin-bottom:2px}
.card .cap{color:var(--ink2);font-size:14px;margin:0 0 10px}
.chart{position:relative;height:260px}
.legend{display:flex;gap:18px;font-size:13px;color:var(--ink2);margin:6px 0 2px}
.legend span::before{content:"";display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle;background:var(--s1)}
.legend span.m::before{background:var(--s2)}
table{width:100%;border-collapse:collapse;font-size:14px;margin:10px 0 4px}
th,td{text-align:left;padding:8px 8px;border-bottom:1px solid var(--hair);vertical-align:top;overflow-wrap:anywhere}
.tw{overflow-x:auto;max-width:100%}
.tile .value{overflow-wrap:anywhere}
th{color:var(--ink2);font-weight:600}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr.us td{font-weight:600}
.rec{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:16px 18px;margin:12px 0}
.rec-head{display:flex;gap:14px;align-items:flex-start;margin-bottom:8px}
.score{flex:none;min-width:58px;text-align:center;background:var(--wash);border-radius:8px;padding:6px 8px;font-size:22px;font-weight:600;line-height:1.1}
.score small{display:block;font-size:11px;font-weight:400;color:var(--ink2)}
.rec p{margin:6px 0}
.lay{color:var(--ink2)}
.pc{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:10px 0}
.pc p{margin:4px 0;font-size:15px}
.owner{font-size:13px;color:var(--muted)}
ul{padding-left:20px}
li{margin:6px 0}
.note{font-size:14px;color:var(--ink2)}
details summary{cursor:pointer;color:var(--ink2)}
@media (max-width:640px){.pc{grid-template-columns:1fr}h1{font-size:25px}.chart{height:230px}}
</style>
</head>
<body>
<main>
<h1>Ultimate Personality Test: ranking plan for the next two weeks</h1>
<p class="sub">Keyword "personality test", page programs.clearerthinking.org/personality-test.html. Built __STAMP__ from Search Console (through __THROUGH__), Ahrefs (SERP of Oct 17), URL Inspection, Wayback, the team repo and a local Lighthouse run.</p>

<div class="verdict">
<p><strong>The blunt version.</strong> #1 in two weeks is not on the table. The page ranks organic #7 in the US with 126 referring domains and a URL rating of 5; the #1 page has 5,547 referring domains and sits on a DR 86 domain, and an AI Overview, a "People also ask" box and sitelinks now stand between #1 and us. What is on the table in two weeks: get back onto page 1 on phones (lost around Sep 28), recover the clicks that went with it, and move one or two places by fixing the things only CT can fix (its own title, its own links, its own page).</p>
<p>Three of the ten actions below are already written or half done: the title fix has been sitting unmerged in a branch since Sep 23, the internal links are a Wix and template edit, and the PAA answers are a rewrite of a FAQ that already exists.</p>
</div>

<div class="tiles">
<div class="tile"><div class="label">US position, last 28 days</div><div class="value">7.0 / 8.2</div><div class="delta">desktop / mobile, exact query</div></div>
<div class="tile"><div class="label">Mobile impressions, week of Sep 28</div><div class="value">11.2K</div><div class="delta bad">from 30.0K the week before (-63%)</div></div>
<div class="tile"><div class="label">Clicks, exact query</div><div class="value">270</div><div class="delta bad">Oct 1-18, vs 2,802 in May</div></div>
<div class="tile"><div class="label">Referring domains to the page</div><div class="value">126</div><div class="delta">#1 result: 5,547. #4 result: 918</div></div>
</div>

<h2>What happened on Sep 28</h2>
<p>Mobile impressions for the exact query fell by two thirds in one week and have not recovered; desktop did not move. The rest of the site, the subdomain, the page itself (unchanged since Jul 31, Lighthouse mobile 100, LCP 1.8 s, crawled as mobile on Oct 21 with the right canonical) and user engagement (mobile engagement rate 95% or better all through) are all clean. The reported mobile position moved only from 8.8 to 9.5 while impressions fell 63%: that pattern is a page sitting at the edge of mobile page 1 and slipping under it, where Google stops counting impressions. Two things coincide: Google's September spam update (Sep 24 to Oct 8) and a new video-thumbnail feature on this SERP (absent Sep 15, present Oct 17). I could not separate the two; the remedy is the same either way, one or two positions.</p>

<div class="card">
<h3>Weekly impressions for "personality test", UPT page</h3>
<p class="cap">Full weeks starting Mon Jun 29 to Mon Oct 12, 2026. Hairlines mark the Jul 21 title change and the Sep 28 week.</p>
<div class="legend"><span>Desktop</span><span class="m">Mobile</span></div>
<div class="chart"><canvas id="c_impr" role="img" aria-label="Weekly desktop and mobile impressions; mobile falls from about 30 thousand to 11 thousand in the week of Sep 28 while desktop stays near 18 thousand"></canvas></div>
</div>
<div class="card">
<h3>Weekly clicks for "personality test", UPT page</h3>
<p class="cap">Same weeks. Mobile clicks went from about 100 a week to 25.</p>
<div class="legend"><span>Desktop</span><span class="m">Mobile</span></div>
<div class="chart"><canvas id="c_clicks" role="img" aria-label="Weekly desktop and mobile clicks; mobile drops from about 100 to 25 in the week of Sep 28"></canvas></div>
</div>

<h2>What happened before that: the June click loss and the July title</h2>
<p>Clicks for the query were 2,802 in May and 1,135 in July. The obvious suspect was the Jul 21 relaunch, which replaced the title "Free Scientific Personality Test: Briggs-Myers, Big 5 &amp; More" with "Ultimate Personality Test | ClearerThinking.org". The weekly data clears it: click-through had already fallen from 1.5% to 0.5% on desktop by the last week of June, and it rose after the new title went live (0.98% in the first week). So the title fix in the Sep 23 branch is still worth shipping, but as a click lever, not as the explanation for the drop. The June loss lines up with a slip of about one position and a reported core update (May 21 to Jun 2); I cannot confirm that update from Google's own dashboard.</p>

<div class="card">
<h3>Monthly click-through rate for "personality test", UPT page</h3>
<p class="cap">May to Oct 2026 (Oct through the 18th), percent of impressions clicked.</p>
<div class="legend"><span>Desktop</span><span class="m">Mobile</span></div>
<div class="chart"><canvas id="c_ctr" role="img" aria-label="Monthly click-through rate; desktop falls from 1.5 percent in May to 0.6 in July and 0.4 in October, mobile from 0.74 to about 0.3"></canvas></div>
</div>
<div class="card">
<h3>Monthly average position for "personality test", UPT page</h3>
<p class="cap">Impression-weighted. Lower is better; the axis is reversed so up means better.</p>
<div class="legend"><span>Desktop</span><span class="m">Mobile</span></div>
<div class="chart"><canvas id="c_pos" role="img" aria-label="Monthly average position; both devices near 7.4 in May, 8.2 to 9.5 in October"></canvas></div>
</div>

<h2>The results page today (US, Ahrefs, Oct 17)</h2>
<div class="tw"><table>
<thead><tr><th>#</th><th>Result</th><th class="num">DR</th><th class="num">UR</th><th class="num">Ref. domains</th><th>Kind</th></tr></thead>
<tbody>__SERP__</tbody>
</table></div>
<p class="note">The keyword: 248,000 US searches a month (654,000 worldwide), difficulty 79, 56% on phones, 73% of searches end in an organic click. The UPT is one of ten sources cited inside the AI Overview, which is worth keeping. The two pages beating us from weaker domains (#4 at DR 37, #5 at DR 46) both put the questions in the HTML and lead their titles with "Free Personality Test"; our page shows Google a 3,000-word explainer and a button.</p>

<h2>Timeline</h2>
<div class="tw"><table><tbody>__TIMELINE__</tbody></table></div>

<h2>What to do, ranked</h2>
<p class="note">Score 10 means do it without question; 1 means do not. Each item names the owner, because three of them live in Josh's repo (willfind/clearer-thinking-programs-static).</p>
__RECS__

<h2>What not to do</h2>
<ul>__DONTS__</ul>

<h2>Internal link audit (what CT controls today)</h2>
<ul>
<li>Google's URL Inspection knows one internal referrer for the page (the "full list of all personality types" post) and three external ones.</li>
<li>The homepage links the page with the anchor "Free Personality Test" (good) and also the old url via an image.</li>
<li>The All Tools page links the OLD url (personality.html, a 301) three times with the anchor "Start".</li>
<li>Five personality posts link the old url ("how accurate are personality test frameworks", "can you really trust personality tests", "announcing UPT 2.0", "what causes anxiety", "personality differences between men and women"); three have no link at all ("how many traits", "PersonalityMap", "gender and the tail end"). CT's research PDF on clearerresearch.org links the old url too.</li>
<li>The page itself links to no CT page except the accuracy study, and carries no structured data and no Open Graph tags.</li>
<li>The default program template (src/templates/program.liquid) is shared by every other tool page, so one footer line reaches ~150 pages.</li>
</ul>

<h2>Method and caveats</h2>
<p class="note">Search Console: domain property, exact query filter, impression-weighted positions, data through __THROUGH__ (Google's 3-day lag). Ahrefs: SERP overview US on Oct 17, backlink reports for the exact url, keyword overview. URL Inspection API for crawl and canonical state. Wayback Machine for the title history (seven captures, 2025-07 to 2026-10-15). The team repo for the Jul 21 launch, the 301 and the unmerged Sep 23 branch. Lighthouse 12 run locally on mobile emulation because the PageSpeed Insights quota was exhausted, so there is no field (CrUX) data here. The Ahrefs SERP capture for Sep 15 looked unreliable (news and forum results at the top) and was not used. Spam-link classification is from Ahrefs' is_spam flag and the page titles, which name the link-dump services. The backlink and memory records show no link buying by CT.</p>
<details><summary>Table view of the weekly series</summary>
<div class="tw"><table><thead><tr><th>Week of</th><th class="num">Impr. desktop</th><th class="num">Impr. mobile</th><th class="num">Clicks desktop</th><th class="num">Clicks mobile</th><th class="num">Pos. desktop</th><th class="num">Pos. mobile</th></tr></thead><tbody>__WEEKLY__</tbody></table></div>
</details>
</main>
<script>
const D = __DATA__;
function css(v){return getComputedStyle(document.documentElement).getPropertyValue(v).trim();}
function series(rows, key, device){const weeks=[...new Set(rows.map(r=>r.week||r.month))].sort();return weeks.map(w=>{const r=rows.find(x=>(x.week||x.month)===w&&x.device===device);return r?r[key]:null;});}
function labels(rows){return [...new Set(rows.map(r=>r.week||r.month))].sort();}
function fmtLabel(l){if(l.length===7){return new Date(l+"-15T12:00:00").toLocaleString("en-US",{month:"short"});}const d=new Date(l+"T12:00:00");return d.toLocaleString("en-US",{month:"short",day:"numeric"});}
const marks = {id:"marks", afterDraw(c){const x=c.scales.x, ctx=c.ctx, want=c.config.options.marks||[]; want.forEach(m=>{const i=c.data.labels.indexOf(m.at); if(i<0)return; const px=x.getPixelForValue(i); ctx.save(); ctx.strokeStyle=css("--hair"); ctx.lineWidth=1; ctx.beginPath(); ctx.moveTo(px,c.chartArea.top); ctx.lineTo(px,c.chartArea.bottom); ctx.stroke(); ctx.font="12px system-ui,sans-serif"; ctx.textAlign=m.align||"left"; const tx=px+(m.align==="right"?-4:4), ty=c.chartArea.top+12, tw=ctx.measureText(m.text).width; ctx.fillStyle=css("--surface"); ctx.fillRect(m.align==="right"?tx-tw-3:tx-3, ty-11, tw+6, 15); ctx.fillStyle=css("--muted"); ctx.fillText(m.text, tx, ty); ctx.restore();});}};
Chart.register(marks);
function mk(id, rows, key, opts){
  const ls=labels(rows), s=css("--surface");
  const ds=[["DESKTOP","Desktop","--s1"],["MOBILE","Mobile","--s2"]].map(([dev,name,v])=>({label:name,data:series(rows,key,dev),borderColor:css(v),backgroundColor:css(v),borderWidth:2,pointRadius:4,pointHoverRadius:6,pointBorderColor:s,pointBorderWidth:2,tension:0.2,spanGaps:true}));
  return new Chart(document.getElementById(id),{type:"line",data:{labels:ls,datasets:ds},options:Object.assign({
    responsive:true,maintainAspectRatio:false,interaction:{mode:"index",intersect:false},
    plugins:{legend:{display:false},tooltip:{callbacks:{title:i=>i[0].label,label:c=>c.dataset.label+": "+(opts.fmt||(v=>v.toLocaleString()))(c.parsed.y)}}},
    scales:{x:{grid:{display:false},border:{display:false},ticks:{color:css("--muted"),maxRotation:0,autoSkip:true,callback:(v,i)=>fmtLabel(ls[i])}},
            y:Object.assign({grid:{display:false},border:{display:false},ticks:{color:css("--muted"),callback:v=>(opts.tick||(x=>x>=1000?(x/1000)+"K":x))(v)}},opts.y||{})}
  },opts.extra||{})});
}
const WK=[{at:"2026-07-20",text:"Jul 21: new title"},{at:"2026-09-28",text:"Sep 28",align:"right"}];
mk("c_impr",D.weekly,"impressions",{y:{beginAtZero:true},extra:{marks:WK}});
mk("c_clicks",D.weekly,"clicks",{y:{beginAtZero:true},extra:{marks:WK}});
mk("c_ctr",D.monthly,"ctr",{y:{beginAtZero:true},tick:v=>v+"%",fmt:v=>v.toFixed(2)+"%",extra:{marks:[{at:"2026-07",text:"Jul 21: new title"}]}});
mk("c_pos",D.monthly,"position",{y:{reverse:true,suggestedMin:6,suggestedMax:10},tick:v=>v,fmt:v=>v.toFixed(2),extra:{marks:[{at:"2026-07",text:"Jul 21: new title"}]}});
</script>
</body>
</html>
"""
html = (html.replace("__STAMP__", stamp).replace("__THROUGH__", data["data_through"]).replace("__SERP__", serp_rows)
        .replace("__TIMELINE__", tl_rows).replace("__RECS__", rec_html).replace("__DONTS__", dont_html)
        .replace("__WEEKLY__", wk_rows).replace("__DATA__", json.dumps({"weekly": weekly, "monthly": monthly})))
assert "—" not in html, "em dash found"
OUT.write_text(html)
print("wrote", OUT, len(html), "bytes;", "em-dash-free")
