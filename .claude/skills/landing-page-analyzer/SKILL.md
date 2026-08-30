---
name: landing-page-analyzer
description: >-
  Analyze a landing page (LP) for conversion and answer the only question that
  matters: "what could I change to convert more people?" Use whenever the user
  wants a landing page / sales page / signup page / pricing page critiqued,
  audited, or improved for conversions, or asks about CRO (conversion rate
  optimization), conversion, bounce, message match, value proposition, CTA, or
  why a page isn't converting. Input is usually a URL (sometimes a screenshot or
  pasted copy). Fetches and maps the full page, then audits it against
  research-backed CRO + copywriting best practices (Baymard, NN/g, CXL, Unbounce,
  Stanford/Fogg web credibility, Cialdini, plus the Hopkins/Caples/Ogilvy/Schwartz
  copy canon) and returns findings PRIORITIZED BY LIKELY CONVERSION IMPACT —
  highest-leverage changes first — not a flat checklist. Can also rewrite the
  page. For CT pages, applies Clearer Thinking brand voice. Distinct from
  ct-ad-designer (that makes ad creatives; this analyzes destination pages).
---

# Landing Page Analyzer

You audit a landing page and tell the user **what to change to convert more people** — ranked by likely impact, grounded in research, specific and actionable. Not a generic checklist dump: a prioritized diagnosis.

## The one rule that governs everything

**The goal of every landing page is conversion.** Every observation must connect to that: *does this help or hurt the odds that a visitor takes the one desired action?* If a finding doesn't plausibly move conversion, cut it or rank it last. Lead with the few changes most likely to move the number; don't bury a fatal message-match break under a note about button color.

## The knowledge base (read before auditing)

Two research-backed references live in `references/` — read both when doing a real audit:

- **`references/cro-and-design.md`** — page structure, attention ratio / message match, above-the-fold, value proposition, visual hierarchy (F/Z patterns, gaze), cognitive load, CTA design, trust/credibility (Stanford/Fogg), social proof, forms, page speed/mobile, urgency, objection handling, testing. Ends with a tiered audit checklist.
- **`references/copywriting.md`** — headline, awareness & market sophistication (Schwartz), benefits-vs-features, Voice-of-Customer mining, clarity/readability (cognitive fluency), "you"-focus, structure/flow, proof/specificity, CTA copy, objection-handling copy, emotion+logic (Cialdini, loss aversion), microcopy. Ends with a copy-audit checklist.

Both flag **myths vs. tested findings** (e.g. button color is about contrast, not a magic color; "above the fold is everything" is false; "shorter form always wins" is conditional) and tag every claim by evidence strength. **Don't assert a "best practice" as law** — the strongest reliable wins are message match, value-prop clarity, focus/attention ratio, friction reduction, and proof. Frame the rest as hypotheses to test.

**Brand voice for CT pages:** if the page is Clearer Thinking's, any copy you suggest must obey the CT voice guardrails in `ct-ad-designer/references/copywriting.md` (no clickbait/hype/fake urgency, never talk down, benefit-honest, "you", American English). The shared copy canon (Hopkins/Caples/Ogilvy/Schwartz/Cialdini) is consistent across both skills.

## Workflow

### Phase 1 — Pin the conversion goal & the traffic
Before judging anything, establish:
- **What is the ONE action** this page should drive (buy, subscribe, book a call, start a free trial, submit a lead)? If the page itself is ambiguous about this, that ambiguity is itself a Tier-1 finding.
- **Who is the traffic and how warm** (cold paid ad? the CT email list? retargeting?) — this sets the expected **awareness stage** (Schwartz) and therefore what the page *should* open with. Ask the user if it's not obvious and it changes the verdict; otherwise state your assumption.
- **What drove the click** (the ad/email/link), so you can judge **message match**. If the user mentions a campaign or email, hold the page's promise against that source's promise.

### Phase 2 — Fetch & map the page (don't analyze blind)
- **WebFetch the URL** and extract the full page in reading order: headline + subhead, every section heading, body copy/bullets, **every CTA and its exact text**, all social proof/testimonials/stats/logos, pricing and how it's framed, FAQ/objection content, any free-trial/guarantee/risk-reversal, form fields, images/video (what they show + where), and whether the **global site nav** is present.
- For things WebFetch can't see, **say so and flag them to check**: actual **page-load speed**, **mobile** rendering, gaze direction of hero faces, the **post-click flow** (how many steps from CTA to done), autoplay/pop-ups. These are often real conversion killers — don't silently skip them; list them as "verify directly."
- If given a **screenshot or pasted copy** instead, work from that and note what you couldn't see.

### Phase 3 — Audit against the references, scoring for impact
Walk both checklists (`cro-and-design.md` §15 and `copywriting.md` §14). For each issue found, judge **likely conversion impact** (how many visitors it plausibly affects × how much) and **confidence/evidence strength**. Pay special attention to the high-leverage few:
1. **Focus / attention ratio** — one goal, one action; is the global nav and competing links/CTAs leaking visitors?
2. **Message match** — does the page's promise match the source that drove the click?
3. **Value proposition clarity** — passes the 5-second test? clear what / for whom / why better?
4. **Friction** — form length, number of decisions (Hick's), choice overload, page speed, mobile.
5. **Proof & trust** — specific named social proof near the decision point; credibility surface.
6. **Risk reversal & objections** — guarantee/free-trial/"no card"; are top objections answered where they arise?
7. **CTA** — placement/repetition, contrast, and first-person value-led copy.
8. Then copy quality, hierarchy, visuals, microcopy.

### Phase 4 — Deliver a prioritized diagnosis (the output)
Don't return a flat list. Return:

```
## Verdict — <one line: what this page is trying to do + the single biggest thing holding it back>

## Tier 1 — Highest conversion impact (fix first)
- **<Finding>.** <Why it costs conversions, grounded in a principle/source.> → <Specific change to make.>
...

## Tier 2 — Strong improvements
...

## Tier 3 — Polish & credibility
...

## Verify directly (couldn't see from the page)
- page speed / mobile / post-click flow / gaze / etc.

## If you only do three things
1. … 2. … 3. …
```

Rules for the output:
- **Every finding ties to conversion** and, where it helps, cites the principle or source ("attention ratio," "message match," "Baymard: each field is friction," "Stanford/Fogg surface credibility").
- **Be specific and prescriptive** — quote the page's actual headline/CTA/copy and give the concrete replacement or change, not "improve the headline."
- **Rank by impact, flag confidence.** Separate "this is a known high-leverage lever" from "this is a hypothesis worth A/B testing." Never present an untested micro-tweak as a guaranteed win.
- **Frame as testable.** Where appropriate, phrase a change as a hypothesis ("test X because Y"), and note these are best assessed by testing, not decree.
- **Close with the top 3** highest-leverage moves so the user knows where to start.

### Phase 5 — Offer the rewrite (don't assume it)
After the diagnosis, offer to (a) **rewrite the page** top-to-bottom in the recommended structure (hook → problem → solution/mechanism → benefits → proof → objections → offer/risk-reversal → CTA), or (b) **build a dedicated variant** for a specific traffic source (e.g. a campaign/email's promise). Use AskUserQuestion if the direction genuinely forks. For CT pages, write any copy in CT voice and mine real Voice-of-Customer language (e.g. the March 2026 audience survey, n=539) rather than inventing.

## Hard rules
- **Conversion is the only scoreboard.** Aesthetic or "nice to have" notes go last or get cut.
- **Prioritize, always.** A ranked top-few beats an exhaustive flat list every time.
- **Research over hacks.** Lean on the references; call out myths; don't state context-dependent tactics as laws.
- **Specific, quoted, prescriptive.** Name the actual element and the exact change.
- **Don't skip what you can't see** — list speed, mobile, and post-click flow as "verify directly" rather than ignoring them.
- **CT brand voice** governs any suggested copy for Clearer Thinking pages.
