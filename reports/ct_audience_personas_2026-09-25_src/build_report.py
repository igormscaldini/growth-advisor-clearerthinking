"""Build the "Who we are talking to" PDF: CT user personas + audience breakdown.

Section 1 is read straight from the dashboard's personas component
(frontend/components/personas-tab.tsx) so the PDF never drifts from the dashboard.
Section 2 is rendered from datapoints.json next to this script.

Usage (from the repo root):
    .venv/bin/python reports/ct_audience_personas_2026-09-25_src/build_report.py
Outputs the HTML next to the other reports and the PDF to ~/Downloads.
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import json
import re
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TSX = ROOT / "frontend" / "components" / "personas-tab.tsx"
LOGO = ROOT / "assets" / "ct-logo-horizontal.png"
DATA = json.loads((HERE / "datapoints.json").read_text())
HTML_OUT = ROOT / "reports" / "ct_audience_personas_2026-09-25.html"
PDF_OUT = Path.home() / "Downloads" / "CT audience personas 2026-09-25.pdf"

PERSONA_COLORS = ["#1baf7a", "#0885f8", "#f8911b"]  # green, CT blue, CT orange
SECTION_TITLES = [
    ("who", "Who they are"),
    ("wants", "What they want"),
    ("blockers", "What blocks them"),
    ("path", "How they find us"),
    ("money", "How they pay (or don't)"),
    ("voice", "How to talk to them"),
]


# --------------------------------------------------------------------------- dashboard
def load_personas() -> tuple[list[dict], str, list[str]]:
    """Return (personas, intro paragraph, goal bullets) parsed from the TSX component."""
    src = TSX.read_text()
    m = re.search(r"const PERSONAS: Persona\[\] = (\[.*?\n\]);", src, re.S)
    if not m:
        raise SystemExit("PERSONAS array not found in personas-tab.tsx")
    js = "const PERSONAS = " + m.group(1) + ";\nprocess.stdout.write(JSON.stringify(PERSONAS));"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    personas = json.loads(subprocess.check_output(["node", f.name], text=True))

    intro = re.search(r'<p className="mt-2 text-sm[^>]*>(.*?)</p>', src, re.S)
    intro_text = re.sub(r"\s+", " ", intro.group(1)).strip() if intro else ""
    goals_block = src.split("What this means for the goals", 1)[1]
    goals = [re.sub(r"\s+", " ", g).strip() for g in re.findall(r"<li>(.*?)</li>", goals_block, re.S)]
    return personas, intro_text, goals


# --------------------------------------------------------------------------- helpers
def esc(s: str) -> str:
    return html.escape(s, quote=False)


def pct(v: float, n: float) -> str:
    return f"{round(v / n * 100)}%"


def bars(title: str, rows: list, n: int | None = None, color: str = "#0885f8",
         note: str = "", value_fmt=None, max_value: float | None = None, unit: str = "") -> str:
    """Minimalist horizontal bar chart. rows = [(label, value), ...]."""
    values = [r[1] for r in rows]
    mx = max_value or max(values)
    out = [f'<div class="chart avoid"><div class="ch">{esc(title)}'
           + (f'<span class="n">n = {n:,}</span>' if n else "") + "</div>"]
    for label, v in rows:
        if value_fmt:
            right = value_fmt(v)
        elif n:
            right = f"{v:,} <span class='pc'>{pct(v, n)}</span>"
        else:
            right = f"{v:,}{unit}"
        w = max(1.5, v / mx * 100)
        out.append(
            f'<div class="bar"><div class="lb">{esc(label)}</div>'
            f'<div class="track"><div class="fill" style="width:{w:.1f}%;background:{color}"></div></div>'
            f'<div class="val">{right}</div></div>'
        )
    if note:
        out.append(f'<div class="note">{esc(note)}</div>')
    out.append("</div>")
    return "".join(out)


def columns(title: str, labels: list[str], values: list[int], colors: list[str],
            n: int, caption: str = "") -> str:
    mx = max(values)
    cols = []
    for lab, v, c in zip(labels, values, colors):
        h = v / mx * 100
        cols.append(
            f'<div class="col"><div class="cv">{v}</div>'
            f'<div class="cb" style="height:{h:.0f}%;background:{c}"></div>'
            f'<div class="cl">{esc(lab)}</div></div>'
        )
    return (f'<div class="chart avoid"><div class="ch">{esc(title)}<span class="n">n = {n:,}</span></div>'
            f'<div class="cols">{"".join(cols)}</div>'
            + (f'<div class="caption">{caption}</div>' if caption else "") + "</div>")


def tiles(items: list[tuple[str, str]]) -> str:
    cells = "".join(f'<div class="tile"><div class="v">{v}</div><div class="l">{esc(l)}</div></div>' for v, l in items)
    return f'<div class="tiles avoid" style="grid-template-columns:repeat({len(items)},1fr)">{cells}</div>'


def callout(title: str, body: str, color: str = "#0885f8") -> str:
    return (f'<div class="callout avoid" style="border-left-color:{color}">'
            f'<div class="ct">{esc(title)}</div><div>{body}</div></div>')


def ul(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"


def h2(num: str, text: str, sub: str = "") -> str:
    return (f'<div class="h2"><span class="num">{num}</span>{esc(text)}</div>'
            + (f'<p class="sub">{sub}</p>' if sub else ""))


def h3(text: str, sub: str = "") -> str:
    return f'<div class="h3">{esc(text)}</div>' + (f'<p class="sub">{sub}</p>' if sub else "")


def grid(*cells: str, cols: int = 2) -> str:
    return f'<div class="grid g{cols}">' + "".join(f"<div>{c}</div>" for c in cells) + "</div>"


# --------------------------------------------------------------------------- section 1
def persona_card(p: dict, color: str) -> str:
    secs = {k: f'<div class="ps"><div class="pt"><span class="dot" style="background:{color}"></span>{t}</div>{ul(p[k])}</div>'
            for k, t in SECTION_TITLES}
    left = secs["who"] + secs["wants"] + secs["blockers"]
    right = secs["path"] + secs["money"] + secs["voice"]
    return f"""
<div class="persona page" style="border-top-color:{color}">
  <div class="ph">
    <div class="pn">{esc(p['name'])}</div>
    <div class="ptag">{esc(p['tagline'])}</div>
    <div class="pshare"><span class="pill" style="background:{color}">Share</span>{esc(p['share'])}</div>
  </div>
  <div class="grid g2 pg">
    <div>{left}</div>
    <div>{right}</div>
  </div>
  <div class="pfoot">Sources: {esc(" · ".join(p['evidence']))}</div>
</div>"""


def section1(personas: list[dict], intro: str, goals: list[str]) -> str:
    glance_rows = "".join(
        f'<tr><td><span class="sw" style="background:{c}"></span><b>{esc(p["name"])}</b></td>'
        f'<td class="it">{esc(p["tagline"])}</td><td>{esc(p["share"])}</td></tr>'
        for p, c in zip(personas, PERSONA_COLORS)
    )
    out = [f"""
<div class="page">
  {h2("1", "CT user personas", "As shown on the Growth Advisor dashboard (Personas tab). The text below is the dashboard's, reproduced verbatim.")}
  <p class="lead">{esc(intro)}</p>
  <table class="glance avoid">
    <thead><tr><th>Persona</th><th>In one line</th><th>Share of the audience</th></tr></thead>
    <tbody>{glance_rows}</tbody>
  </table>
  {callout("What this means for the goals", ul(goals), "#233b47")}
  <p class="sub" style="margin-top:6mm">Each persona has its own page next: who they are, what they want, what blocks them, how they find Clearer Thinking, whether they pay, and how to talk to them. Sources are listed at the foot of each page.</p>
</div>"""]
    for p, c in zip(personas, PERSONA_COLORS):
        out.append(persona_card(p, c))
    return "".join(out)


# --------------------------------------------------------------------------- section 2
def section2() -> str:
    S = DATA["survey_2026_03"]
    P = DATA["paths"]
    C = DATA["coaching_2024"]
    K = DATA["career_2026_09"]
    B = DATA["buyers_2026_06"]
    blue, navy, orange, green, gold, grey = "#0885f8", "#233b47", "#f8911b", "#1baf7a", "#e5b500", "#8a8a8a"

    # ---- 2.0 sources
    sources = f"""
<div class="page">
  {h2("2", "Audience breakdown", "What the surveys, the Paths quiz and the payment data say, source by source. Every chart names its own n; shares are of the people who answered that question.")}
  <table class="src avoid">
    <thead><tr><th>Source</th><th>What it is</th><th>Size</th></tr></thead>
    <tbody>
      <tr><td><b>Audience survey</b><br>March 2026</td><td>Newsletter readers asked what they value, want, struggle with and who they are. Self-selected; skews to engaged readers.</td><td>{S['respondents']} opened it; 132 to 181 answers per question</td></tr>
      <tr><td><b>Paths quiz</b><br>Jul 2023 to Jul 2026</td><td>The Clearer Thinking Paths tool: people rate priorities, tick goals, problems and identities, then get a personalised plan. Behavioural data from tool users, not just readers.</td><td>{P['runs']:,} runs; {P['assessed']:,} completed the assessment; {P['planned']:,} built a plan; {P['emails']:,} left an email</td></tr>
      <tr><td><b>Coaching-interest survey</b><br>Jul to Nov 2024</td><td>Readers asked whether they would try Clearer Thinking coaching, which type, how often and at what price.</td><td>{C['runs']} runs; {C['answered']} answered the first question; {C['finished']} finished</td></tr>
      <tr><td><b>Career Navigation Survey</b><br>Sep 2026</td><td>Readers asked where they are with their career and what would help, to shape the live career workshop.</td><td>{K['answered']} answered the first question; {K['finished']} finished</td></tr>
      <tr><td><b>Buyer and engagement profile</b><br>Jun 2026</td><td>Stripe charges (trailing 12 months), beehiiv open rates and the GA4 tool funnel (90 days), joined by email. What people do, not what they say.</td><td>{B['buyers']} buyers; about ${B['revenue_12m']/1000:.0f}k; 41k email submits</td></tr>
    </tbody>
  </table>
  {callout("The one-paragraph version", "<p>Clearer Thinking's audience is a curious, college-educated, mostly Anglosphere crowd that calls itself lifelong learners first and self-improvers second, with a large rationalist, science and Effective Altruism overlap. They come for self-understanding and better decisions, and they are blocked by execution, not ambition: procrastination, focus, discipline and anxiety top every list. Politically they lean progressive about three to one, but a real conservative minority reads. They like weekly email, interactive tools and One Helpful Idea, and they are lukewarm on the podcast and video. Advocacy is weak (NPS of minus 5), paywalls feel off-mission to some, and only a third know Clearer Thinking Plus exists. The people who pay are the same people who open the emails, and only a quarter of buyers are on the newsletter.</p>", navy)}
</div>"""

    # ---- 2.1 who they are
    who = f"""
<div class="page">
  {h2("2.1", "Who they are", "Self-described identity in the survey (readers) and the Paths quiz (tool users). The two populations agree on the core and differ at the edges: readers skew older and more academic, Paths users more entrepreneurial and career-focused.")}
  {grid(
    bars("Identity, audience survey (multi-select)", S['identities']['rows'], S['identities']['n'], blue),
    bars("Identity, Paths quiz (multi-select)", P['identities']['rows'], P['identities']['n'], green),
  )}
  {grid(
    bars("Employment status, survey", S['employment']['rows'], S['employment']['n'], navy),
    bars("Industry, survey (top 11)", S['industry']['rows'], S['industry']['n'], navy),
  )}
  {grid(
    columns("Political self-position, survey (minus 5 = progressive, plus 5 = conservative)", S['political']['labels'], S['political']['dist'],
            [blue]*5 + [grey] + [orange]*5, S['political']['n'],
            f"Progressive {pct(S['political']['progressive'], S['political']['n'])} · Center {pct(S['political']['center'], S['political']['n'])} · Conservative {pct(S['political']['conservative'], S['political']['n'])}. Neutrality is not optional."),
    bars("Years of experience, career survey", K['experience']['rows'], K['experience']['n'], orange)
    + bars("Highest education, career survey", K['education']['rows'], K['education']['n'], orange),
  )}
</div>"""

    # ---- 2.2 what they want
    wants = f"""
<div class="page">
  {h2("2.2", "What they want", "Priorities, goals and the formats they ask for. Decisions, plans and self-understanding lead everywhere; understanding the world and societal impact trail, even in an audience that identifies with Effective Altruism.")}
  {grid(
    bars("Paths quiz: how high a priority is this right now? (average, 0 to 4)", P['priorities']['rows'], None, green,
         value_fmt=lambda v: f"{v:.2f}", max_value=4, note="About 7,700 ratings per item. Every item sits above the midpoint: a high-intent audience."),
    bars("Survey: high priorities in my life right now (multi-select)", S['priorities']['rows'], S['priorities']['n'], blue),
  )}
  {grid(
    bars("Survey: major goals right now (top 16 of 46)", S['goals']['rows'], S['goals']['n'], blue),
    bars("Paths quiz: goals ticked (top 10)", P['goals']['rows'], P['goals']['n'], green)
    + bars("Survey: least-chosen goals", S['goals_bottom']['rows'], S['goals_bottom']['n'], grey),
  )}
</div>
<div class="page">
  {h3("Formats, tools and topics", "What readers say they value and want more of. Interactive tools and One Helpful Idea tie for most valued; the podcast and video are the least valued formats by a wide margin.")}
  {grid(
    bars("Most valuable Clearer Thinking offering (single choice)", S['most_valuable']['rows'], S['most_valuable']['n'], blue),
    bars("Least valuable offering (single choice)", S['least_valuable']['rows'], S['least_valuable']['n'], orange),
  )}
  {grid(
    bars("Kinds of tools they want more of (multi-select)", S['tool_types']['rows'], S['tool_types']['n'], blue),
    bars("Tool ideas they would use (multi-select)", S['tool_ideas']['rows'], S['tool_ideas']['n'], navy),
  )}
  {grid(
    bars("Topics to cover more (multi-select)", S['topics']['rows'], S['topics']['n'], navy),
    bars("Ideal cadence for the main newsletter", S['frequency']['rows'], S['frequency']['n'], blue)
    + bars("How should the main newsletter's length change?", S['length']['rows'], S['length']['n'], blue),
  )}
</div>
<div class="page">
  {h3("Goals by life area (Paths quiz)", "The leading objective within each category the quiz asks about, as a share of the 7,889 assessment-takers.")}
  <div class="grid g4">{"".join(f"<div>{bars(cat, rows, P['goals']['n'], green)}</div>" for cat, rows in P['goal_categories'][:4])}</div>
  <div class="grid g3">{"".join(f"<div>{bars(cat, rows, P['goals']['n'], green)}</div>" for cat, rows in P['goal_categories'][4:])}</div>
  {grid(
    bars("Tools that end up in Paths plans (top 12)", P['tools']['rows'], P['tools']['n'], green, note=P['tools']['note']),
    bars("Platforms they would follow Clearer Thinking on", S['platforms']['rows'], S['platforms']['n'], blue,
         note="Most respondents picked none: email is the channel they want.")
    + bars("Offerings they already knew about", S['aware_offerings']['rows'], S['aware_offerings']['n'], blue),
  )}
</div>"""

    # ---- 2.3 what blocks them
    tension = ("Procrastination is the number one problem in every dataset, with anxiety, focus, discipline and motivation "
               "right behind it. Mental health is core, not fringe: anxiety, low mood and loneliness rank near the top of the "
               "Paths list, so a meaningful slice of the audience arrives in distress. 'More to read' backfires with this group; "
               "follow-through tools, small next steps and encouragement work.")
    blocks = f"""
<div class="page">
  {h2("2.3", "What blocks them", "The same problems top both datasets, in almost the same order. The gap between goals (better version of myself, greater impact) and blockers (procrastination, focus, discipline) is the signature tension of this audience.")}
  {grid(
    bars("Survey: big challenges right now (multi-select)", S['problems']['rows'], S['problems']['n'], orange),
    bars("Paths quiz: problems ticked (top 10)", P['problems']['rows'], P['problems']['n'], orange),
  )}
  {grid(
    callout("Execution, not ambition", tension, orange),
    bars("World trends that concern them most (multi-select)", S['concerns']['rows'], S['concerns']['n'], navy),
  )}
  {h3("Friction with Clearer Thinking", "Themes from the open answers about what holds readers back, what would make them use CT more, and what stops them sharing.")}
  <table class="qual"><thead><tr><th>Theme</th><th>In their words</th></tr></thead><tbody>
    {"".join(f"<tr><td><b>{esc(t)}</b></td><td>{esc(q)}</td></tr>" for t, q in S['qual_friction'])}
  </tbody></table>
</div>"""

    # ---- 2.4 advocacy
    nps = S['nps']
    advocacy = f"""
<div class="page">
  {h2("2.4", "Advocacy and awareness", "How likely readers are to recommend Clearer Thinking, whether they know about the paid membership, and what stops them from sharing.")}
  {tiles([(f"{nps['score']}", "Net Promoter Score (n = 181)"), (pct(nps['promoters'], nps['n']), "Promoters (9 to 10)"), (pct(nps['passives'], nps['n']), "Passives (7 to 8)"), (pct(nps['detractors'], nps['n']), "Detractors (0 to 6)"), (pct(S['plus_aware']['rows'][1][1], S['plus_aware']['n']), "Knew Clearer Thinking Plus exists")])}
  {grid(
    columns("How likely are you to recommend Clearer Thinking to a friend? (0 to 10)", [str(i) for i in range(11)], nps['dist'],
            ["#e24b4a"]*7 + [gold]*2 + [green]*2, nps['n'],
            "Polarised rather than indifferent: almost as many 9s and 10s as 5s and 6s. The headline strategic problem for word of mouth."),
    bars("Aware of Clearer Thinking Plus?", S['plus_aware']['rows'], S['plus_aware']['n'], blue,
         note="Awareness, not willingness, is the first gap for the membership.")
    + callout("When they reach for Clearer Thinking", ul(S['qual_reach']), blue),
  )}
  {callout("What they compare Clearer Thinking to", "<p>" + esc(", ".join(S['comparables'])) + ". Readers place Clearer Thinking in the rationalist and applied-psychology corner of the internet, and several said no other site offers the same apolitical deep thinking.</p>", navy)}
</div>"""

    # ---- 2.5 who pays
    ov = B['overlap']
    pays = f"""
<div class="page">
  {h2("2.5", "Who pays and who engages", "Behavioural data from Stripe, beehiiv and GA4 (June 2026). Buying and engaging are the same people seen twice: engaged subscribers buy at more than twice the rate of unengaged ones, and buyers who are on the newsletter open at twice the baseline.")}
  {tiles([(f"{B['buyers']}", "Buyers, trailing 12 months"), (f"${B['order']['median']}", "Median order"), (f"${B['order']['mean']}", "Mean order"), (f"{B['order']['repeat_pct']}%", "Buy again"), (f"{ov['buyers_subscribed_pct']}%", "Buyers on the newsletter"), (f"{ov['engaged_buy_multiple']}x", "Buy rate, engaged vs unengaged subscribers")])}
  {grid(
    bars("What buyers buy (share of buyers)", B['products']['rows'], None, navy, value_fmt=lambda v: f"{v}%", max_value=100),
    bars("Open rate of mature subscribers by the tool that acquired them", B['open_by_tool']['rows'], None, blue, value_fmt=lambda v: f"{v:g}%", max_value=45,
         note="Self-insight tools produce engaged readers; abstract tools produce subscribers who never open. Baseline is about 30%."),
  )}
  {grid(
    bars("Tool funnel, 90 days (GA4)", B['funnel_90d']['rows'], None, green, value_fmt=lambda v: f"{v/1000:.0f}k")
    + bars("Open rate by email type", B['open_by_email']['rows'], None, blue, value_fmt=lambda v: f"{v:g}%", max_value=45),
    bars("Where tool finishers come from (channel)", B['channels']['rows'], None, navy, value_fmt=lambda v: f"{v}%", max_value=100)
    + bars("Where tool finishers are (country)", B['countries']['rows'], None, navy, value_fmt=lambda v: f"{v}%", max_value=100,
           note=B['geo_revenue']),
  )}
</div>"""

    # ---- 2.6 coaching and career
    coaching = f"""
<div class="page">
  {h2("2.6", "Coaching and career demand", "Two reader surveys about paid, human help. Both point the same way: people want a diagnosis first (which path, which problem), then a structured path through the change.")}
  {h3("Coaching-interest survey, 2024")}
  <div class="grid g4">
    <div>{bars("Would you sign up for CT coaching?", C['interest']['rows'], C['interest']['n'], green)}</div>
    <div>{bars("Type of coaching wanted (multi-select)", C['types']['rows'], C['types']['n'], green)}</div>
    <div>{bars("Preferred session frequency", C['frequency']['rows'], C['frequency']['n'], green)}</div>
    <div>{bars("Most they would pay per session", C['pay']['rows'], C['pay']['n'], green)}</div>
  </div>
  <p class="sub">{esc(C['positly'])} Lead coaching copy with behaviour change and root-cause problem solving, pre-empt the "life coach selling obvious tips" image, and price against the $50 to $99 band.</p>
  {h3("Career Navigation Survey, September 2026")}
  <div class="grid g4">
    <div>{bars("Where they are with their career", K['stage']['rows'], K['stage']['n'], orange)}</div>
    <div>{bars("What would help most (single choice)", K['help']['rows'], K['help']['n'], orange)}</div>
    <div>{bars("What they weigh when choosing a path", K['weigh']['rows'], K['weigh']['n'], orange)}</div>
    <div>{bars("Biggest obstacle (coded open answers)", K['obstacles']['rows'], K['obstacles']['n'], orange)}</div>
  </div>
  <p class="sub">Three in four respondents are mid-change. Fit and meaning outrank salary when weighing a path, and the biggest obstacle is choosing: a self-assessment that maps strengths and values to careers beats the live workshop itself three to one. Half have more than ten years of experience and 43% hold a graduate degree.</p>
</div>"""

    # ---- 2.7 mapping to personas
    mapping = f"""
<div class="page">
  {h2("2.7", "Reading the data through the personas", "Which parts of the breakdown each persona draws on. Shares are estimates from self-reported data, not measurements.")}
  <table class="map avoid">
    <thead><tr><th></th><th><span class="sw" style="background:{PERSONA_COLORS[0]}"></span>Curious Self-Improver</th><th><span class="sw" style="background:{PERSONA_COLORS[1]}"></span>Rigorous Rationalist</th><th><span class="sw" style="background:{PERSONA_COLORS[2]}"></span>Overwhelmed Striver</th></tr></thead>
    <tbody>
      <tr><td>Identity signals</td><td>Lifelong learner (80% survey, 54% Paths), self-improvement and science enthusiast, writer, health enthusiast, retiree</td><td>Rationalist (34% survey, 26% Paths), Effective Altruist (26% / 18%), philosopher (20% / 22%), academic, software engineer</td><td>Student (20% survey, 18% Paths), not employed (30%), career focused (22% Paths), first-career choosers in the career survey</td></tr>
      <tr><td>What they ask for</td><td>Personal assessments, thinking-skill developers, weekly email, One Helpful Idea, tools with clear results</td><td>Changing minds, scout mindset, forecasting, IQ, risk; citations, transcripts, diverse voices, open tools</td><td>Focus, emotional overwhelm, self-talk, daily intention; therapeutic tools; coaching (88% would try it)</td></tr>
      <tr><td>What blocks them</td><td>Procrastination, motivation, focus, time management</td><td>Paywalls feel off-mission; trust wobbles on thin sourcing; hard to share with non-rationalist friends</td><td>Anxiety (37% / 44%), low mood (30%), career uncertainty (41%), low confidence, loneliness; low disposable income; India about 25% of sign-ups</td></tr>
      <tr><td>Where the money is</td><td>The $9 Personality PDF (50% of buyers); engaged subscribers buy at 2.2x</td><td>Cognitive Assessment (27% of buyers); the natural CT+ member once they know it exists (31% do)</td><td>Rarely buys today; coaching at $50 to $99 a session and follow-through products are the realistic offers</td></tr>
      <tr><td>Front-door tools</td><td>Intrinsic Values Test (41% opens), Ultimate Personality Test (31%)</td><td>Faulty Reasoning, Nuanced Thinking; Predict Correlations brings them in but yields 17% opens</td><td>Mood and productivity tools, paid campaigns (24% of finishers); many stop at the email gate</td></tr>
    </tbody>
  </table>
  {callout("Caveats", ul([
      "Both surveys and the Paths quiz are self-selected: they describe engaged readers and tool users, not the 700k-record list or the casual visitor.",
      "Survey n's are small (132 to 181 per question), so differences under about eight points are noise.",
      "Paths tool selections are inflated by eight pre-checked defaults; the three questions added in July 2026 (resource interests, role, content diet) have too few answers to report yet.",
      "The career survey's 'why change' question was shown to everyone because of a GuidedTrack truthiness bug, so it is not charted here.",
      "The buyer profile is a June 2026 snapshot of the trailing twelve months; re-run it before quoting it as current.",
      "Percentages in this document were recomputed from the published chart data and the raw GuidedTrack exports; the dashboard's persona copy was corrected on 2026-09-25 to match.",
  ]), grey)}
</div>"""

    return sources + who + wants + blocks + advocacy + pays + coaching + mapping


# --------------------------------------------------------------------------- page
CSS = """
:root{--blue:#0885f8;--navy:#233b47;--gold:#fecb02;--orange:#f8911b;--paper:#f9f1e3;--grey:#f5f5f5;
      --ink:#303030;--muted:#737373;--light:#a6a6a6;--line:#e4e4e4;--green:#1baf7a}
*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}
html,body{margin:0;padding:0}
body{font-family:"Avenir Next","Avenir","Inter","Helvetica Neue",Helvetica,Arial,sans-serif;color:var(--ink);
     font-size:9.4pt;line-height:1.42}
p{margin:0 0 2.2mm}
ul{margin:0;padding-left:4mm}
li{margin:0 0 1.3mm}
b{font-weight:600}
.page{break-after:page}
.page:last-child{break-after:auto}
.avoid{break-inside:avoid}
.grid{display:grid;gap:0 7mm;align-items:start}
.g2{grid-template-columns:1fr 1fr}
.g3{grid-template-columns:1fr 1fr 1fr}
.g4{grid-template-columns:1fr 1fr 1fr 1fr;gap:0 5mm}
/* cover */
.cover{height:257mm;display:flex;flex-direction:column}
.cover .logo{height:8mm;width:auto;align-self:flex-start}
.eyebrow{font-size:8.5pt;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--blue);margin-top:26mm}
.cover h1{font-size:30pt;line-height:1.08;color:var(--navy);margin:3mm 0 3mm;font-weight:700;letter-spacing:-.01em}
.cover .subtitle{font-size:14pt;color:var(--ink);margin:0 0 2mm;font-weight:500}
.cover .stamp{font-size:9.5pt;color:var(--muted);margin:0 0 10mm}
.cover .lead{font-size:10.5pt;max-width:150mm}
.toc{margin-top:8mm;border-top:1px solid var(--line);padding-top:5mm;max-width:150mm}
.toc .t{font-size:8.5pt;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:2mm}
.toc .row{display:grid;grid-template-columns:12mm 1fr;margin:0 0 1.2mm;font-size:10pt}
.toc .row .k{color:var(--blue);font-weight:600}
.toc .sub{display:grid;grid-template-columns:12mm 1fr;margin:0 0 .8mm;font-size:9pt;color:var(--muted)}
.cover .foot{margin-top:auto;font-size:8.5pt;color:var(--muted);border-top:1px solid var(--line);padding-top:3mm}
/* headings */
.h2{font-size:17pt;font-weight:700;color:var(--navy);margin:0 0 1.5mm;letter-spacing:-.01em}
.h2 .num{color:var(--blue);margin-right:3mm;font-variant-numeric:tabular-nums}
.h3{font-size:11.5pt;font-weight:700;color:var(--navy);margin:5mm 0 1.2mm}
.sub{color:var(--muted);font-size:9pt;margin:0 0 4mm;max-width:170mm}
.lead{font-size:10pt;margin:0 0 4mm;max-width:170mm}
/* charts */
.chart{margin:0 0 5mm}
.ch{font-size:8.8pt;font-weight:600;color:var(--navy);margin:0 0 1.6mm;display:flex;justify-content:space-between;gap:3mm;align-items:baseline}
.ch .n{font-weight:400;color:var(--light);font-size:7.8pt;white-space:nowrap}
.bar{display:grid;grid-template-columns:minmax(0,54%) 1fr 17mm;align-items:center;gap:0 2mm;margin:0 0 1.15mm;font-size:8.2pt;line-height:1.15}
.g4 .bar{grid-template-columns:minmax(0,60%) 1fr 13mm;font-size:7.6pt}
.g3 .bar{grid-template-columns:minmax(0,58%) 1fr 14mm;font-size:7.8pt}
.g3 .bar,.g4 .bar{margin-bottom:1mm}
.lb{color:var(--ink);overflow-wrap:anywhere}
.track{height:5px;background:#eceff2;border-radius:3px;overflow:hidden}
.fill{height:100%;border-radius:3px}
.val{text-align:right;color:var(--ink);font-variant-numeric:tabular-nums;white-space:nowrap}
.val .pc{color:var(--muted);font-size:7.4pt;margin-left:.6mm}
.note,.caption{font-size:7.8pt;color:var(--muted);margin-top:1.4mm;line-height:1.35}
.cols{display:flex;align-items:flex-end;gap:1.2mm;height:30mm;margin-top:2mm}
.col{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%}
.cb{width:100%;border-radius:2px 2px 0 0;min-height:1px}
.cv{font-size:7pt;color:var(--muted);margin-bottom:.6mm;font-variant-numeric:tabular-nums}
.cl{font-size:7pt;color:var(--muted);margin-top:1mm}
/* tiles, callouts, tables */
.tiles{display:grid;gap:3mm;margin:0 0 5mm}
.tile{background:var(--grey);border-radius:2.5mm;padding:3mm 3.2mm}
.tile .v{font-size:16pt;font-weight:700;color:var(--navy);line-height:1.1;letter-spacing:-.01em}
.tile .l{font-size:7.6pt;color:var(--muted);margin-top:1mm;line-height:1.3}
.callout{background:var(--paper);border-left:1mm solid var(--blue);border-radius:0 2.5mm 2.5mm 0;padding:3mm 4mm;margin:0 0 5mm;font-size:9pt}
.callout .ct{font-weight:700;color:var(--navy);margin-bottom:1.2mm}
.callout p{margin:0}
.callout ul{padding-left:4mm}
table{border-collapse:collapse;width:100%;font-size:8.6pt;margin:0 0 5mm}
th{text-align:left;font-size:7.8pt;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:600;padding:0 2.5mm 1.6mm 0;border-bottom:1px solid var(--line)}
td{vertical-align:top;padding:2mm 2.5mm 2mm 0;border-bottom:1px solid var(--line)}
tr:last-child td{border-bottom:none}
.glance td:first-child{width:44mm;white-space:nowrap}
.glance .it{font-style:italic;color:var(--muted)}
.src td:first-child{width:36mm}
.src td:last-child{width:44mm;color:var(--muted)}
.qual td:first-child{width:34mm}
.qual td{padding:1.6mm 2.5mm 1.6mm 0}
.map th,.map td{font-size:8.2pt}
.map td:first-child{width:26mm;color:var(--muted);font-weight:600}
.sw{display:inline-block;width:2.6mm;height:2.6mm;border-radius:50%;margin-right:1.6mm;vertical-align:-0.2mm}
/* personas */
.persona{border-top:2.4mm solid;padding-top:4mm}
.pn{font-size:18pt;font-weight:700;color:var(--navy);letter-spacing:-.01em;line-height:1.1}
.ptag{font-size:10.5pt;font-style:italic;color:var(--muted);margin:1.5mm 0 2mm;max-width:165mm}
.pshare{font-size:8.6pt;color:var(--ink);margin-bottom:5mm}
.pill{display:inline-block;color:#fff;font-size:7pt;font-weight:600;letter-spacing:.08em;text-transform:uppercase;padding:.6mm 2mm;border-radius:3mm;margin-right:2mm;vertical-align:.2mm}
.pg{gap:0 8mm}
.ps{margin:0 0 4.5mm}
.pt{font-size:8pt;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0 0 1.5mm}
.dot{display:inline-block;width:2.2mm;height:2.2mm;border-radius:50%;margin-right:1.8mm;vertical-align:.1mm}
.ps li{margin-bottom:1.6mm;font-size:9.2pt}
.pfoot{font-size:7.8pt;color:var(--light);border-top:1px solid var(--line);padding-top:2mm;margin-top:1mm}
"""


def logo_b64() -> str:
    """The logo PNG, cropped to its visible pixels so padding does not inflate it."""
    import io
    from PIL import Image, ImageChops

    im = Image.open(LOGO).convert("RGBA")
    bbox = im.split()[-1].getbbox()
    if bbox is None or bbox == (0, 0) + im.size:
        bbox = ImageChops.difference(im.convert("RGB"), Image.new("RGB", im.size, (255, 255, 255))).getbbox()
    buf = io.BytesIO()
    im.crop(bbox).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def build_html(stamp: str) -> str:
    personas, intro, goals = load_personas()
    logo = logo_b64()
    cover = f"""
<div class="cover page">
  <img class="logo" src="data:image/png;base64,{logo}" alt="Clearer Thinking">
  <div class="eyebrow">Clearer Thinking · Growth Advisor</div>
  <h1>Who we are talking to</h1>
  <div class="subtitle">CT user personas and a breakdown of the audience</div>
  <div class="stamp">Generated {stamp}</div>
  <p class="lead">Three personas that cover most of the Clearer Thinking audience, taken from the Growth Advisor dashboard, followed by the evidence behind them: the March 2026 audience survey, the Paths quiz (20,201 runs), the coaching and career surveys, and the June 2026 buyer and engagement profile. Use the personas to sanity-check a tool, a campaign or an email; use the breakdown when you need the underlying numbers.</p>
  <div class="toc">
    <div class="t">Contents</div>
    <div class="row"><span class="k">1</span><span>CT user personas, as on the dashboard</span></div>
    <div class="sub"><span></span><span>The Curious Self-Improver · The Rigorous Rationalist · The Overwhelmed Striver · What this means for the goals</span></div>
    <div class="row"><span class="k">2</span><span>Audience breakdown from surveys and the Paths quiz</span></div>
    <div class="sub"><span>2.1</span><span>Who they are</span></div>
    <div class="sub"><span>2.2</span><span>What they want</span></div>
    <div class="sub"><span>2.3</span><span>What blocks them</span></div>
    <div class="sub"><span>2.4</span><span>Advocacy and awareness</span></div>
    <div class="sub"><span>2.5</span><span>Who pays and who engages</span></div>
    <div class="sub"><span>2.6</span><span>Coaching and career demand</span></div>
    <div class="sub"><span>2.7</span><span>Reading the data through the personas, and caveats</span></div>
  </div>
  <div class="foot">Sources: Clearer Thinking audience survey (March 2026, 539 respondents); Clearer Thinking Paths export (Jul 2023 to Jul 2026, 20,201 runs); coaching-interest survey (GuidedTrack 29944, 2024, 276 runs); Career Navigation Survey (GuidedTrack 38720, Sep 2026, 143 respondents); Stripe, beehiiv and GA4 buyer and engagement profile (June 2026). Dashboard: growth-advisor-clearerthinking.vercel.app</div>
</div>"""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Who we are talking to: Clearer Thinking personas and audience breakdown</title>
<style>{CSS}</style></head>
<body>
{cover}
{section1(personas, intro, goals)}
{section2()}
</body></html>"""


def render_pdf(html_path: Path, pdf_path: Path, stamp: str) -> None:
    from playwright.sync_api import sync_playwright

    footer = (
        '<div style="width:100%;font-family:Helvetica,Arial,sans-serif;font-size:7pt;color:#a6a6a6;'
        'padding:0 16mm;display:flex;justify-content:space-between">'
        f'<span>Clearer Thinking · Who we are talking to · {stamp[:10]}</span>'
        '<span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>'
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page()
        page.goto(html_path.as_uri())
        page.wait_for_load_state("networkidle")
        page.pdf(
            path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=False,
            margin={"top": "14mm", "bottom": "16mm", "left": "16mm", "right": "16mm"},
            display_header_footer=True, header_template="<div></div>", footer_template=footer,
        )
        browser.close()


def main() -> None:
    stamp = dt.datetime.now().strftime("%Y-%m-%d %I:%M%p").replace("AM", "am").replace("PM", "pm")
    HTML_OUT.write_text(build_html(stamp))
    render_pdf(HTML_OUT, PDF_OUT, stamp)
    print(f"html: {HTML_OUT}\npdf:  {PDF_OUT}")


if __name__ == "__main__":
    main()
