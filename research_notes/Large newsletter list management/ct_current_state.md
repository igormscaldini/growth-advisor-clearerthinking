# Clearer Thinking on beehiiv: current state of list management and sends

Read-only audit, pulled 2026-11-06 through the beehiiv connector (tool named for each fact) plus `dig` for DNS. Publication: "Clearer Thinking" (`pub_d0ed5a5f-...`, created on beehiiv 2025-04-09). Nothing in beehiiv was changed. Aggregates only.

STATUS OF THIS FILE: work in progress (first save). Sections marked PENDING are still being gathered.

## Summary of the current state

PENDING (written last, once every section is filled).

## 1. List size and composition

Source: `get_publication_stats` (all_time, last_12_months, last_4_weeks), `get_subscriber_history` (all_time, monthly), `get_subscriber_growth` (2026-10-01 to 2026-11-06, UTC), all called 2026-11-06.

- Active subscribers now: 678,349 (`current_active_subscribers`). This is higher than the "roughly 500k" assumed in the brief and the "~520k" in older project notes. The public description still says "Join over 300,000 subscribers".
- All-time: 819,245 subscriptions created, 140,896 churned (17.2% of everything ever added), net 678,349.
- Last 12 months: 408,136 new, 127,348 churned, net +280,788. Open rate 29.3%, click rate 1.59% (beehiiv publication-level figures).
- Last 4 weeks: 52,707 new, 24,652 churned, net +28,055. Open rate 18.3%, click rate 1.92%.
- Free vs paid: beehiiv paid tiers are not how CT sells memberships (CT+ is sold through Stripe). Segment metrics report 0 premium subscribers on the engaged segment. See section 9 for `list_tiers`.

### Active subscribers by month (get_subscriber_history, count as of the 1st)

| Date | Active subscribers | Change |
|---|---|---|
| 2025-07-01 | 49,271 | first non-zero month |
| 2025-09-01 | 48,912 | flat |
| 2025-10-01 | 199,900 | +150,988 (bulk import, Sep 2025) |
| 2025-11-01 | 388,252 | +188,352 (bulk import, Oct 2025) |
| 2025-12-01 | 397,561 | +9,309 |
| 2026-01-01 | 431,764 | +34,203 |
| 2026-02-01 | 439,234 | +7,470 |
| 2026-03-01 | 440,140 | +906 |
| 2026-04-01 | 444,769 | +4,629 |
| 2026-05-01 | 449,008 | +4,239 |
| 2026-06-01 | 448,471 | -537 |
| 2026-07-01 | 447,851 | -620 |
| 2026-08-01 | 447,525 | -326 |
| 2026-09-01 | 626,349 | +178,824 (bulk import, Aug 2026) |
| 2026-10-01 | 649,447 | +23,098 |
| 2026-11-06 | 678,349 | +28,902 |

Verified against the brief: the two bulk imports are real and show as steps in the history: about +339k across Sep and Oct 2025 and about +179k in Aug 2026. Between March and August 2026 the active count was flat (440k to 448k) even though tools were adding sign-ups daily, so churn was roughly cancelling organic growth in that period.

### Acquisition channel (get_publication_stats, `acquisition_sources`)

The source rows of the all-time call sum to 678,352, which equals the current active count (678,349) to within 3. So this breakdown counts subscribers who are active today by how they were acquired, not everyone ever acquired (my inference from the totals; beehiiv does not document it in the tool output).

| Channel (grouped from the rows) | Active today, all time | Share | Acquired in last 12 months and still active | Last 4 weeks |
|---|---|---|---|---|
| import | 554,993 | 81.8% | 222,077 | 895 |
| api (tools and quizzes, incl. api google/cpc 2,430 and api meta/cpc 691) | 121,722 | 17.9% | 121,722 | 37,992 |
| embed (beehiiv embed forms) | 1,154 | 0.2% | 1,148 | 182 |
| recommendation (other beehiiv newsletters) | 454 | 0.1% | 439 | 4 |
| website + referral | 29 | 0.0% | 26 | 1 |

- Four of every five active subscribers (82%) carry the import channel. Note the import channel also contains the original migration of the pre-beehiiv list, so "import" is not the same as "cold": it mixes long-standing readers with the bulk additions.
- The API channel (tools) accounts for all 121,722 non-import sign-ups of note, all within the last 12 months, consistent with tools creating subscribers through the API only since 2026-03-09 (project CLAUDE.md).
- In the last 4 weeks the source rows sum to 39,074 while `new_subscribers` is 52,707: about 13.6k of the people who joined in those 4 weeks are already no longer active (see anomalies).

### Daily growth, 2026-10-01 to 2026-11-06 (get_subscriber_growth, UTC days)

- Totals: 48,819 subscribed, 19,908 unsubscribed, 290 resubscribed, net +28,911.
- Median day: 465 new, 252 unsubscribes. Excluding the Oct 21 to 23 spike, the mean is 520 new per day (34 days). So the "300 to 500 a day" in the brief is about right, slightly low.
- Spike: Oct 21, 22, 23 brought 9,215 + 15,536 + 6,401 = 31,152 sign-ups (the "Who Attracts You" tool going viral, per the project memory note on the drip copy). Those same three days had 1,072 + 1,560 + 4,091 = 6,723 unsubscribes.
- Unsubscribes cluster on send days: Oct 6 (971), Oct 8 (575), Oct 14 (725), Oct 16 (584), Oct 30 (697), Nov 6 (1,548, partial day, right after the Nov 5 to 6 whole-list send). On non-send days they run about 150 to 250.

## 2. Segments

Source: `list_segments` (123 segments in total), `get_segment` for definitions. PENDING: definitions and last-calculated dates for most segments. First facts:

| Segment | Type | Members | Condition (`where`) | Paused | Last processed (UTC) |
|---|---|---|---|---|---|
| Engaged Reades - Open > 40% | dynamic | 133,383 | `open_rate >= 40 AND status = 'active'` | true | 2026-11-05 07:46 |
| Unengaged | dynamic | 124,881 | `signup_date < NOW() - INTERVAL '6 months' AND status = 'active' AND unique_sends >= 1 AND open_rate(within: '6 months') = 0` | true | 2026-07-10 07:55 |
| Never Opened an Email | static | 120,674 | `open_rate = 0 AND signup_date <= NOW() - INTERVAL '3 months'` | false | 2026-08-08 01:11 |

## 3. Who receives what (recent sends)

PENDING. First fact: the newest post (Nov 6 00:16 UTC, "How (And Why) to Reason More Complexly - Variant B", subject "How to think more complexly") was sent to the segment "CT Audience - All Subscribers" with no exclusions: 324,369 sent, 321,536 delivered, 18,460 suppressions, 75,996 unique opens (23.64%), 432 unique verified clicks, 1,299 unsubscribes, 4 spam reports, 76 hard and 2,961 soft bounces (`get_post`, `get_post_stats`).

## 4. Per-mailbox-provider results

PENDING.

## 5. Sending setup

Source so far: `get_publication`, `get_publication_settings`.

- Email (sending) domain configured on the publication: `ohi.clearerthinking.net`, status reported by beehiiv: `warming_up`.
- Branded link (click-tracking) domain: `elink7ea.clearerthinking.net`, status `live`.
- Web domain: none (the beehiiv site lives at clearerthinking.beehiiv.com). `white_labeled: true`, private branding on.
- Sender name: "ClearerThinking.org"; `use_post_author_name: false`.
- Publication time zone: Eastern Time (US and Canada).
- DNS records: PENDING.

## 6. Sign-up and opt-in

Source so far: `get_publication_settings`.

- Double opt-in: OFF (`double_opt_in: false`).
- Smart nudge (beehiiv's reminder to unconfirmed subscribers): off (`smart_nudge: false`).
- `require_subscriber_approval: false`; `allow_subscription_pauses: false` (a reader cannot pause instead of unsubscribing).
- Subscriber tags that exist (`get_publication`): attractiveness-study, career_workshop_sep2026, dating_app, unanswered_outreach.
- PENDING: forms, signup flows, custom fields, preference lists, opt-in email.

## 7. Automations

PENDING.

## 8. Hygiene evidence

PENDING.

## 9. Reader feedback and preferences

PENDING.

## Could not determine

PENDING.

## Anomalies

PENDING.
