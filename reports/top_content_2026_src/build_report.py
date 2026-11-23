"""datapoints.json -> reports/top_content_2026.html"""
import html
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
d = json.loads((HERE / "datapoints.json").read_text())
e = html.escape


def art_rows(rows, start=1):
    return "".join(f"<tr><td>{i}</td><td><a href='{e(r['url'])}'>{e(r['title'])}</a>{'<div class=n>' + e(r['note']) + '</div>' if r['note'] else ''}</td>"
                   f"<td>{r['emailed']}</td><td>{r['recipients']:,}</td><td>{r['unique_opens']:,}</td><td>{r['web_users']:,}</td><td><b>{r['reach']:,}</b></td></tr>"
                   for i, r in enumerate(rows, start))


tools = d["tools"]
tool_rows = "".join(f"<tr><td>{i}</td><td><a href='{e(r['url'])}'>{e(r['title'])}</a>{'<div class=n>' + e(r['note']) + '</div>' if r.get('note') else ''}</td>"
                    f"<td>{e(str(r['launched'])[:7])}</td><td><b>{r['users']:,}</b></td></tr>" for i, r in enumerate(tools["top10"], 1))
now = datetime.now().strftime("%Y-%m-%d %I:%M%p").lower()
head = "<tr><th>#</th><th>Article</th><th>First emailed</th><th>Recipients</th><th>Unique opens</th><th>Web users (not from our email)</th><th>People reached</th></tr>"
page = f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Top content of 2026</title><style>
body{{font:15px/1.5 -apple-system,Avenir,sans-serif;color:#1d2b36;background:#fff;max-width:1000px;margin:32px auto;padding:0 16px}}
h1{{margin-bottom:0}} .sub{{color:#6b7785;margin-top:4px}} table{{border-collapse:collapse;width:100%;margin:12px 0 28px}}
th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid #e5e9ee;vertical-align:top}} th{{font-size:13px;color:#6b7785;font-weight:600}}
td:nth-child(n+3),th:nth-child(n+3){{text-align:right;white-space:nowrap}} a{{color:#1f6fb2;text-decoration:none}} .n{{font-size:12px;color:#8a95a1}}
details summary{{cursor:pointer;color:#1f6fb2;margin-bottom:8px}} li{{margin-bottom:6px}}
</style></head><body>
<h1>Top articles and tools of 2026</h1><p class=sub>Data Jan 1 to {d['window']['end']} &middot; generated {now}</p>
<h2>Top 10 articles</h2>
<p>People reached = unique email opens summed over every send of the article + GA4 users who reached the blog post from any source except our own emails (so email readers are not counted twice; email-scanner sessions, source "(not set)", left out). Articles = blog posts first published in 2026; a study report page is merged into its article.</p>
<table>{head}{art_rows(d['top10'])}</table>
<details><summary>All {len(d['articles'])} articles</summary><table>{head}{art_rows(d['articles'])}</table></details>
<h2>Top 10 tools</h2>
<p>Total GA4 users on the tool's own pages on programs.clearerthinking.org, {tools['window']['start']} to {tools['window']['end']}. Partner-branded copies (/p/&lt;partner&gt;/) left out.</p>
<table><tr><th>#</th><th>Tool</th><th>Launched</th><th>Users in 2026</th></tr>{tool_rows}</table>
<h2>Read before using these lists</h2><ul>
<li><b>The article ranking is 99% email opens.</b> Web users add a few hundred per article; only the AI study (13.2k, mostly the 1440 newsletter), What Stands Between You and Reality (10.1k, 1440) and Nowstalgia (7.5k, an untagged one-day spike on Mar 11) get real outside traffic.</li>
<li><b>Opens mostly track send size.</b> Four of the top six went to the whole list (600k+ recipients, since Oct 16); spring articles went to ~250-440k. Ranked by open rate instead, a different list comes out. Opens also include Apple Mail auto-opens.</li>
<li>Places 9 to 15 are within 8k of each other: practically tied.</li>
<li>Not counted as articles (no 2026 blog post): {'; '.join(e(x['label']) + f" ({x['unique_opens']:,} opens)" for x in d['not_blog_sends'])}.</li>
<li>Tools: Who Attracts You? (1.2M users from three viral waves) was left out of the Nov 19 tools ranking at Igor's request and is included here. How Rational Are You, Really? got 63% of its 2026 sessions from paid ads. GA4 undercounts the Ultimate Personality Test (blind to visitors who never click Start since Jul 21, and to everything Jul 22 - Aug 10).</li>
<li>Not ranked: {'; '.join(e(k) + (f" ({v:,} users)" if v else '') for k, v in tools['not_ranked'].items())}. Partner copies much larger than the tool's own pages: {'; '.join(f"{e(k)} {v:,}" for k, v in tools['partner_copies_much_larger'].items())}.</li>
<li>December is not in yet: re-run before the year-end send (fetch_data.py, fetch_ga4.py, analysis.py, build_report.py in reports/top_content_2026_src/).</li>
</ul></body></html>"""
out = HERE.parent / "top_content_2026.html"
out.write_text(page)
print(out)
