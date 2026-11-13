# ClearerThinking Growth Goals

_Last updated: 2026-07-10_

The current growth targets I'm working toward. Updated by Igor; referenced by the advisor whenever discussing goals, progress, or strategy.

## Targets

1. **$120,000 gross revenue**
   - Source: Stripe gross volume (sum of successful charges, pre-refund)
   - Tracked on dashboard: *Total Revenue (Gross)* card

2. **100 active Stripe subscribers**
   - Source: Stripe subscriptions with `status = active`
   - Tracked on dashboard: not yet a dedicated card — currently visible via Stripe directly

3. **#1 Google ranking for the keyword "personality test"**
   - Page: https://programs.clearerthinking.org/personality-test.html
   - Source: Google Search Console (average position for the query)
   - Tracked: GSC (not on dashboard yet)

4. **100,000 average unique opens per campaign**
   - Definition (Igor, 2026-11-13): average `unique_opens` per **regular edition** over the **last 90 days**: One Helpful Idea and the main article newsletter only. No promo emails, tool launches, workshop invitations or reminders, coaching blasts, the Monthly Debrief or test sends.
   - An edition = every send on one US Eastern day summed (segment, A/B and sending-domain splits are one campaign); it counts when it reached 100,000+ readers, opened at 15%+ (re-sends to dormant readers open under 10%) and is at least 3 days old (opens still accruing). Rules in `newsletter_editions.py`.
   - Source: beehiiv posts API (`stats.email.unique_opens` / `recipients`), computed in `beehiiv_avg_unique_opens_per_campaign()` in `data_layer.py`
   - Baselines: ~86,000 across ~78 all-time campaigns to 100k+ readers (Jul 2026, the old definition); 88,628 across 19 regular editions Aug 15 to Nov 10, 2026 (the new one)
   - Tracked on dashboard: *Progress against goals* row. Target is hard-coded as `AVG_OPENS_TARGET` in `frontend/components/goals-table.tsx`; set the real target there and here together.
   - _(Replaced the former "200,000 engaged subscribers" goal, which used the beehiiv "Engaged Reades - Open > 40%" segment.)_

5. **$5,000 MRR** _(provisional)_
   - Source: Stripe current MRR snapshot
   - Tracked on dashboard: *MRR* card + Progress-against-goals row
   - Note: derived target — ~revenue-per-active-subscriber × the 100-subscriber goal. Replace with Igor's real figure when set. Also hard-coded as `MRR_TARGET` in `frontend/components/goals-table.tsx`; update both together.

## Notes

- Timeframes for each goal aren't specified yet — annual? end of 2026? Add when known.
- Some goals don't have dedicated dashboard cards yet (active subs count, GSC ranking for the keyword). Worth adding if you start tracking weekly.
