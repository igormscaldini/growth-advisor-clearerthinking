# ClearerThinking Growth Goals

_Last updated: 2026-05-09_

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

4. **200,000 engaged subscribers**
   - Definition: subscribers in the beehiiv segment **"Engaged Reades - Open > 40%"** (open rate > 40%)
   - Source: beehiiv segments API
   - Tracked on dashboard: *Engaged Readers* card

5. **$5,000 MRR** _(provisional)_
   - Source: Stripe current MRR snapshot
   - Tracked on dashboard: *MRR* card + Progress-against-goals row
   - Note: derived target — ~revenue-per-active-subscriber × the 100-subscriber goal. Replace with Igor's real figure when set. Also hard-coded as `MRR_TARGET` in `frontend/components/goals-table.tsx`; update both together.

## Notes

- Timeframes for each goal aren't specified yet — annual? end of 2026? Add when known.
- Some goals don't have dedicated dashboard cards yet (active subs count, GSC ranking for the keyword). Worth adding if you start tracking weekly.
