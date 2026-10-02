"""Build reports/newsletter_topics_2026-10-02.html: topics covered by the CT newsletter in 2026.

    python build_report.py

Inputs (both beside this script):
  data/posts_2026.json   every confirmed beehiiv send of 2026 (id, title, subject, publish_date, recipients)
  classification.json    the single source for which sends form an edition, each edition's topic, format
                         and byline, and why every other send was left out. Edit it to re-bucket.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "newsletter_topics_2026-10-02.html"
ET = ZoneInfo("America/New_York")
MIXED = "Mixed (newsletter swap)"


def load() -> tuple[list[dict], dict]:
    posts = json.loads((HERE / "data" / "posts_2026.json").read_text())
    cls = json.loads((HERE / "classification.json").read_text())
    ids = [i for e in cls["editions"] for i in e["post_ids"]] + [i for g in cls["excluded"] for i in g["post_ids"]]
    assert sorted(ids) == sorted(p["id"] for p in posts), "every send must be classified exactly once"
    assert all(e["topic"] in cls["topics"] and e["format"] in cls["formats"] for e in cls["editions"])
    return posts, cls


def editions_with_dates(posts: list[dict], cls: dict) -> list[dict]:
    by_id = {p["id"]: p for p in posts}
    out = []
    for e in cls["editions"]:
        first = min(by_id[i]["publish_date"] for i in e["post_ids"])
        out.append({**e, "date": datetime.fromtimestamp(first, tz=timezone.utc).astimezone(ET)})
    return sorted(out, key=lambda e: e["date"])


def topic_order(eds: list[dict]) -> list[tuple[str, int]]:
    counts = Counter(e["topic"] for e in eds)
    return sorted(counts.items(), key=lambda kv: (kv[0] == MIXED, -kv[1], kv[0]))


def bars(rows: list[tuple[str, int, list[str]]], total: int) -> str:
    top = max(n for _, n, _ in rows)
    out = []
    for label, n, titles in rows:
        tip = escape(json.dumps(titles, ensure_ascii=False), quote=True)
        out.append(
            f'<div class="bar-row" data-tip="{tip}" data-label="{escape(label)}">'
            f'<div class="bar-label">{escape(label)}</div>'
            f'<div class="bar-track"><div class="bar" style="width:{n / top * 100:.1f}%"></div>'
            f'<span class="bar-val">{n} <span class="muted">({n / total * 100:.0f}%)</span></span></div></div>')
    return "\n".join(out)


def count_table(head: tuple[str, str], rows: list[tuple[str, int]], total: int | None = None) -> str:
    body = "".join(f"<tr><td>{escape(k)}</td><td class='num'>{v}</td>"
                   + (f"<td class='num muted'>{v / total * 100:.0f}%</td>" if total else "") + "</tr>" for k, v in rows)
    share = "<th class='num'>Share</th>" if total else ""
    return f"<table><thead><tr><th>{head[0]}</th><th class='num'>{head[1]}</th>{share}</tr></thead><tbody>{body}</tbody></table>"


def build() -> str:
    posts, cls = load()
    eds = editions_with_dates(posts, cls)
    n = len(eds)
    order = topic_order(eds)
    by_topic = defaultdict(list)
    for e in eds:
        by_topic[e["topic"]].append(e)

    topic_bars = bars([(t, c, [f'{e["date"]:%b %-d}: {e["title"]}' for e in by_topic[t]]) for t, c in order], n)

    months = sorted({(e["date"].year, e["date"].month) for e in eds})
    grid = Counter((e["topic"], (e["date"].year, e["date"].month)) for e in eds)
    month_tot = Counter((e["date"].year, e["date"].month) for e in eds)
    grid_head = "".join(f"<th class='num'>{datetime(y, m, 1):%b}</th>" for y, m in months)
    grid_rows = ""
    for t, c in order:
        cells = "".join(f"<td class='cell'><span class='dot d{min(grid[(t, m)], 3)}'>{grid[(t, m)]}</span></td>" if grid[(t, m)]
                        else "<td class='cell'></td>" for m in months)
        grid_rows += f"<tr><td>{escape(t)}</td>{cells}<td class='num'>{c}</td></tr>"
    grid_foot = "".join(f"<td class='num'>{month_tot[m]}</td>" for m in months)

    fmt = Counter(e["format"] for e in eds).most_common()
    people = Counter()
    for e in eds:
        guests = [b for b in e["bylines"] if b.endswith("(guest)")]
        for b in e["bylines"]:
            if b not in guests:
                people[b] += 1
        if guests:
            people["Guest authors"] += 1
        if not e["bylines"]:
            people["No byline in the email"] += 1
    people_rows = sorted(people.items(), key=lambda kv: (kv[0] in ("Guest authors", "No byline in the email"), -kv[1], kv[0]))

    ed_rows = ""
    for e in eds:
        title = f'<a href="{escape(e["url"])}">{escape(e["title"])}</a>' if e["url"] else escape(e["title"])
        note = f'<div class="note">{escape(e["note"])}</div>' if e["note"] else ""
        by = ", ".join(e["bylines"]) or "<span class='muted'>None stated</span>"
        ed_rows += (f"<tr><td class='nowrap'>{e['date']:%b %-d}</td><td>{title}{note}</td><td>{escape(e['topic'])}</td>"
                    f"<td class='muted'>{escape(', '.join(e['also_touches']))}</td><td>{escape(e['format'])}</td><td>{by}</td></tr>")

    ed_sends = sum(len(e["post_ids"]) for e in eds)
    ex_rows = f"<tr><td>Counted: content editions</td><td class='num'>{ed_sends}</td><td>{n} editions. Split sends and re-sends of the same edition are merged.</td></tr>"
    for g in cls["excluded"]:
        ex_rows += f"<tr><td>Left out: {escape(g['group'])}</td><td class='num'>{len(g['post_ids'])}</td><td>{escape(g['note'])}</td></tr>"
    ex_rows += f"<tr class='total'><td>All beehiiv sends in 2026</td><td class='num'>{len(posts)}</td><td></td></tr>"

    first, last = eds[0]["date"], eds[-1]["date"]
    stamp = datetime.now().strftime("%Y-%m-%d %I:%M%p").lower()
    n_topics = sum(1 for t, _ in order if t != MIXED)
    html = TEMPLATE.format(
        stamp=stamp, n=n, n_posts=len(posts), n_out=len(posts) - ed_sends, n_topics=n_topics, n_months=len(months),
        first=f"{first:%b %-d}", last=f"{last:%b %-d}", topic_bars=topic_bars, grid_head=grid_head, grid_rows=grid_rows,
        grid_foot=grid_foot, fmt_table=count_table(("Format", "Editions"), fmt, n),
        people_table=count_table(("Byline", "Editions"), people_rows), ed_rows=ed_rows, ex_rows=ex_rows)
    assert "—" not in html, "no em dashes"
    return html


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CT newsletter topics, 2026</title>
<style>
:root {{ --surface:#fcfcfb; --card:#ffffff; --text:#0b0b0b; --text2:#52514e; --muted:#85837d; --line:#e7e6e1;
  --series:#2a78d6; --d1:rgba(42,120,214,.16); --d2:rgba(42,120,214,.36); --d3:rgba(42,120,214,.60); }}
@media (prefers-color-scheme: dark) {{ :root {{ --surface:#1a1a19; --card:#222221; --text:#ffffff; --text2:#c3c2b7;
  --muted:#8f8e86; --line:#34342f; --series:#3987e5; --d1:rgba(57,135,229,.22); --d2:rgba(57,135,229,.45); --d3:rgba(57,135,229,.72); }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--surface); color:var(--text); font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
main {{ max-width:1040px; margin:0 auto; padding:40px 20px 72px; }}
h1 {{ font-size:28px; line-height:1.2; margin:0 0 6px; }}
h2 {{ font-size:18px; margin:44px 0 4px; }}
.sub {{ color:var(--text2); margin:0; }}
.lede {{ color:var(--text2); margin:0 0 16px; max-width:760px; }}
.muted {{ color:var(--muted); }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; margin:28px 0 0; }}
.tile {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
.tile b {{ display:block; font-size:28px; line-height:1.15; }}
.tile span {{ color:var(--text2); font-size:13px; }}
.bar-row {{ display:grid; grid-template-columns:250px 1fr; align-items:center; gap:12px; padding:5px 6px; border-radius:6px; cursor:default; }}
.bar-row:hover {{ background:var(--card); }}
.bar-label {{ text-align:right; color:var(--text2); }}
.bar-track {{ display:flex; align-items:center; gap:8px; }}
.bar {{ height:18px; background:var(--series); border-radius:0 4px 4px 0; min-width:2px; flex:none; max-width:calc(100% - 80px); }}
.bar-val {{ font-variant-numeric:tabular-nums; white-space:nowrap; }}
table {{ border-collapse:collapse; width:100%; font-size:14px; }}
th {{ text-align:left; color:var(--text2); font-weight:600; font-size:12.5px; border-bottom:1px solid var(--line); padding:8px 10px; vertical-align:bottom; }}
td {{ padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.cell {{ text-align:right; padding:5px 10px; }}
.dot {{ display:inline-block; min-width:26px; padding:2px 0; text-align:center; border-radius:5px; font-variant-numeric:tabular-nums; }}
.d1 {{ background:var(--d1); }} .d2 {{ background:var(--d2); }} .d3 {{ background:var(--d3); }}
tr.total td {{ font-weight:600; border-bottom:none; }}
.nowrap {{ white-space:nowrap; }}
.note {{ color:var(--muted); font-size:12.5px; margin-top:2px; }}
a {{ color:inherit; text-decoration:underline; text-decoration-color:var(--muted); text-underline-offset:2px; }}
.two {{ display:grid; grid-template-columns:1fr 1fr; gap:36px; }}
.scroll {{ overflow-x:auto; }}
ul {{ padding-left:20px; color:var(--text2); max-width:800px; }} li {{ margin:6px 0; }}
#tip {{ position:fixed; pointer-events:none; display:none; max-width:440px; background:var(--card); color:var(--text); border:1px solid var(--line);
  border-radius:8px; padding:10px 12px; font-size:13px; box-shadow:0 6px 24px rgba(0,0,0,.14); z-index:5; }}
#tip b {{ display:block; margin-bottom:4px; }} #tip div {{ color:var(--text2); margin:2px 0; }}
@media (max-width:720px) {{ .bar-row {{ grid-template-columns:1fr; gap:2px; }} .bar-label {{ text-align:left; }} .two {{ grid-template-columns:1fr; }} }}
</style></head><body><main>
<h1>Topics covered in the Clearer Thinking newsletter, 2026</h1>
<p class="sub">Content editions sent {first} to {last}, 2026 · source: beehiiv · generated {stamp}</p>

<div class="tiles">
  <div class="tile"><b>{n}</b><span>content editions</span></div>
  <div class="tile"><b>{n_topics}</b><span>topics, plus one mixed-topic swap issue</span></div>
  <div class="tile"><b>{n_months}</b><span>months covered (January to September)</span></div>
  <div class="tile"><b>{n_out} of {n_posts}</b><span>beehiiv sends left out (One Helpful Idea, reminders, promo, tests, recaps)</span></div>
</div>

<h2>Editions by topic</h2>
<p class="lede">Each edition is counted once, under its main topic. Hover a bar to see the editions behind it.</p>
<div id="bars">{topic_bars}</div>

<h2>Topic by month</h2>
<p class="lede">Number of editions per topic in each month (send date, US Eastern).</p>
<div class="scroll"><table><thead><tr><th>Topic</th>{grid_head}<th class="num">Total</th></tr></thead>
<tbody>{grid_rows}<tr class="total"><td>All editions</td>{grid_foot}<td class="num">{n}</td></tr></tbody></table></div>

<div class="two">
  <div><h2>By format</h2><p class="lede">What kind of edition it was.</p>{fmt_table}</div>
  <div><h2>By byline</h2><p class="lede">An edition with two authors counts once for each.</p>{people_table}</div>
</div>

<h2>All {n} editions</h2>
<p class="lede">Titles link to the article or tool. "Also touches" lists a second topic the edition clearly covers; it is not used in the counts above.</p>
<div class="scroll"><table><thead><tr><th>Sent</th><th>Edition</th><th>Main topic</th><th>Also touches</th><th>Format</th><th>Byline</th></tr></thead>
<tbody>{ed_rows}</tbody></table></div>

<h2>What was counted and what was left out</h2>
<p class="lede">Every one of the {n_posts} confirmed beehiiv sends from January 1 to October 2, 2026 falls in exactly one row.</p>
<div class="scroll"><table><thead><tr><th>Group</th><th class="num">Sends</th><th>Notes</th></tr></thead><tbody>{ex_rows}</tbody></table></div>

<h2>How this was put together</h2>
<ul>
<li>Topics were assigned by reading the body of each email, one main topic per edition. Clearer Thinking has no topic tags of its own (beehiiv content tags are empty and the blog only uses "research" and "blog"), so the topic names here were created for this breakdown.</li>
<li>The same edition sent to several segments, across two sending domains, or re-sent with a new subject line counts as one edition.</li>
<li>Tool launches and the first chapter of The 12 Levers are counted because they carry a subject of their own. The emails that only asked for a pre-order, a sign-up or a booking are in the promo row.</li>
<li>"CT research findings" are editions built on Clearer Thinking's own study data. Four of the six have a companion study report on the site.</li>
<li>The classification lives in one file (classification.json, next to the script that builds this page), so any edition can be moved to another topic and the page rebuilt.</li>
</ul>
<div id="tip"></div>
<script>
const tip = document.getElementById('tip');
document.querySelectorAll('.bar-row').forEach(r => {{
  r.addEventListener('mousemove', e => {{
    const items = JSON.parse(r.dataset.tip);
    tip.innerHTML = '<b></b>' + items.map(() => '<div></div>').join('');
    tip.querySelector('b').textContent = r.dataset.label;
    tip.querySelectorAll('div').forEach((d, i) => d.textContent = items[i]);
    tip.style.display = 'block';
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.min(e.clientX + 14, window.innerWidth - w - 8) + 'px';
    tip.style.top = Math.min(e.clientY + 14, window.innerHeight - h - 8) + 'px';
  }});
  r.addEventListener('mouseleave', () => tip.style.display = 'none');
}});
</script>
</main></body></html>
"""

if __name__ == "__main__":
    OUT.write_text(build())
    print(OUT)
