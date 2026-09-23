# Plan: benchmarking Substack-style paywalled-post conversion (draft for Igor, 2026-09-23)

Status: awaiting Igor's evaluation. Nothing below has been run yet beyond a source scan and the CT baseline pull.

## What "conversion of a paywalled post" can mean

Three different metrics hide under the phrase. Which one Igor cares about decides the method.

- A. List-level free-to-paid ratio: paid subscribers as a share of the free list. This is what Substack and beehiiv publish.
- B. Per-post paywall conversion: share of readers who hit the paywall in a post and then pay. Creators rarely publish this; the news industry does ("stop rate" and conversion of stopped readers).
- C. Incremental effect of paywalling: extra paid subs gained versus opens, clicks, unsubscribes and sharing lost. This is the number that decides whether CT should do it.

## Why Substack numbers will not transfer cleanly to CT

- CT+ is a $9 to $179 per month bundle of tools and coaching, not a $10 newsletter (the median paid-newsletter price).
- CT's list is 644k with heavy bulk imports and a 29% open rate; the engaged (>40% opens) segment is ~110k.
- The March 2026 survey says paywalls read as off-mission for the core persona, and only 30% of respondents knew CT+ existed.
- Feasibility: the CT beehiiv publication has zero paid tiers, zero premium offers and only the untouched default paywall block. A live paywalled post cannot ship today.

## Baseline found during scouting

| Metric | CT today | beehiiv median (2026) | Substack median (crowd data) |
|---|---|---|---|
| Paid as % of full list | 0.012% (75 / 644k) | 0.62% | ~3% |
| Paid as % of engaged readers | 0.07% (75 / 110k) | | |
| New paid per month | ~10 (Sep 2026) | | |
| ARPU per paid sub | ~$55/mo (MRR 4,110 / 75) | $10/mo, $100/yr | ~$10/mo |
| Monthly churn (CT+) | ~17% | | |

## Phase 1: desk benchmark (one session, no setup)

Sources to extract, each with numerator, denominator, sample, platform, year and an evidence grade:
- Substack official: On Substack "free vs paid", product analytics posts, the 5-10% claim.
- Crowd-sourced Substack data: yana-g-y (median ~3%, 2-5% normal), Steven Scesa paid/free ratio analyses, bestwriting statistics, reallygoodbusinessideas, Newsletter Circle's bestseller paywall strategies.
- Creator post-level cases: Lori Ballen (8,100 views, 2 paid), The Writing Edge, Substack Writers at Work, others found in the run.
- beehiiv State of Paid Newsletters 2026 (median 0.62%, top quartile 2-5%, top decile 5.5-30.8% by vertical), Press Gazette 2026 pricing and churn, Newsletrix, "Six in a Thousand".
- News-industry paywall benchmarks: Lenfest/Nieman 500-publisher study (median stop rate 1.8%, sustainable at or above 4.2%), Piano subscription benchmarks, Audiencers/INMA, Speciall Media.
- Academic: Aral et al. 2020 (NYT paywall tightening: demand -9.9%, subscriptions +31%), Pattabhiramaiah et al. 2018 (engagement externalities), Sjovaag 2016 (what goes behind the wall).

Method: normalise definitions (subscriptions vs subscribers, imports in the denominator, annual vs monthly, comped accounts), then build a low / median / high table per metric A, B, C and flag conflicts (Substack's 5-10% vs the crowd's 3%).

## Phase 2: CT baseline (half session, existing data)

- Readers per post: avg unique opens ~83k; web views per post from the beehiiv posts API; GA4 pageviews and scroll depth on clearerthinking.org article pages; email click rate 1.87%.
- Check where the article body lives (full text in the email vs teaser linking to Wix). A beehiiv paywall only gates the email and the beehiiv web copy.
- CT+ intake, ARPU, churn, tier mix from Stripe; survey attitudes to paywalls.

## Phase 3: translate to CT scenarios (half session)

Model per paywalled post: readers reaching the wall x conversion (low / median / high from Phase 1) x ARPU x expected lifetime (about 1 / churn). Subtract expected losses (opens, unsubscribes; NYT's -10% demand as the anchor). Compare against current CT+ intake. Output: HTML report in reports/ with a sensitivity table and a go / no-go on a live test.

## Phase 4 (optional): live test design on beehiiv

- Prerequisites: beehiiv paid tier connected to CT's Stripe; comp the existing CT+ members via the beehiiv API synced from Stripe; paywall copy that frames CT+ as membership, not a paywall; UTM plus Stripe metadata for attribution.
- Design: split one send into two random segments (beehiiv A/B tests subject lines only): full article vs preview plus paywall. Primary: CT+ sign-ups within 7 days. Guardrails: unsubscribes, next-send opens, clicks, complaints.
- Power (two-proportion test, alpha 0.05): 40k opens per arm detects 0.02% vs 0.05% (8 vs 20 sign-ups) with 62% power; 80k per arm gives 89%. Plan on 2-4 pooled sends.

## Decisions for Igor

1. Scope: Phases 1-3 only (recommended first), or also Phase 4 design.
2. Which metric matters most: A, B or C (recommended: B and C).
3. Include news-industry paywall data as labelled proxies (recommended: yes).
4. Which CT+ tier the paywall would sell (Supporter $9 is the natural newsletter tier).
