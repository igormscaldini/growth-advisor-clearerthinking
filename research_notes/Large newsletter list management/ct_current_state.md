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

Sources: `list_posts` (status published, newest first; 207 published posts, 1 scheduled, 0 archived), `get_post_stats_batch` for every post from 2026-09-07 to 2026-11-06, `get_post` for the audience and split-test settings, `get_post_stats` for bounces, suppressions and split-test outcomes. Pulled 2026-11-06, so the Nov 5 to 6 sends were under a day old and their opens are still accumulating. Open rate = unique opens / delivered. "Verified clicks" = beehiiv's bot-filtered unique clicks. Rates per 1,000 are per 1,000 delivered and computed by me from the counts.

### Every send above 100 recipients, 2026-09-07 to 2026-11-06 (26 sends)

| Sent (UTC) | Sent (US Eastern) | Post | Audience segment on the post record | Recipients | Delivered | Unique opens | Open rate | Unique verified clicks | Verified click rate | Unsubs | Unsubs per 1,000 | Spam reports | Spam per 1,000 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Nov 06 00:16 | Thu Nov 05 07:16PM | Reason More Complexly, Variant B | CT Audience - All Subscribers (half) | 324,369 | 321,536 | 75,996 | 23.6% | 432 | 0.13% | 1,299 | 4.04 | 4 | 0.012 |
| Nov 05 22:00 | Thu Nov 05 05:00PM | Reason More Complexly, Variant A | CT Audience - All Subscribers (half) | 324,457 | 321,839 | 36,195 | 11.2% | 319 | 0.10% | 412 | 1.28 | 10 | 0.031 |
| Oct 30 00:00 | Thu Oct 29 08:00PM | Supplement Paradox, wave 3 | CT Audience - All Subscribers | 252,169 | 249,412 | 6,485 | 2.6% | 434 | 0.17% | 492 | 1.97 | 49 | 0.196 |
| Oct 26 22:00 | Mon Oct 26 06:00PM | Coaching spots (promo) | Engagement: High, excl. Perfect + Navigators | 72,551 | 72,419 | 28,358 | 39.2% | 316 | 0.44% | 210 | 2.90 | 1 | 0.014 |
| Oct 22 23:00 | Thu Oct 22 07:00PM | Steelman | CT Audience - All Subscribers | 624,751 | 618,717 | 126,355 | 20.4% | 3,375 | 0.55% | 3,457 | 5.59 | 80 | 0.129 |
| Oct 21 03:05 | Tue Oct 20 11:05PM | OHI: Great But Awful | OHI Audience - Engaged Subs | 371,636 | 369,300 | 75,284 | 20.4% | 912 | 0.25% | 716 | 1.94 | 9 | 0.024 |
| Oct 19 15:00 | Mon Oct 19 11:00AM | Supplement Paradox, resend | Haven't Opened the Supplement Paradox | 47,997 | 47,861 | 8,631 | 18.0% | 80 | 0.17% | 105 | 2.19 | 1 | 0.021 |
| Oct 16 17:12 | Fri Oct 16 01:12PM | Supplement Paradox, wave 2 | CT Audience - Engaged Subs | 259,406 | 258,082 | 53,286 | 20.6% | 573 | 0.22% | 575 | 2.23 | 4 | 0.015 |
| Oct 16 12:57 | Fri Oct 16 08:57AM | Supplement Paradox, wave 1 | CT Audience - All Subscribers | 125,521 | 124,258 | 11,847 | 9.5% | 192 | 0.15% | 182 | 1.46 | 7 | 0.056 |
| Oct 14 14:24 | Wed Oct 14 10:24AM | Coaching spots (promo) | Engagement: High, excl. Perfect + Navigators | 18,279 | 18,233 | 6,910 | 37.9% | 85 | 0.47% | 54 | 2.96 | 1 | 0.055 |
| Oct 14 01:51 | Tue Oct 13 09:51PM | OHI: Too Many Stories | OHI Audience - All Subscribers | 358,641 | 356,327 | 71,692 | 20.1% | 831 | 0.23% | 690 | 1.94 | 9 | 0.025 |
| Oct 12 13:37 | Mon Oct 12 09:37AM | Coaching spots (promo) | Engagement: Perfect, excl. Navigators | 6,583 | 6,577 | 5,983 | 91.0% | 103 | 1.57% | 95 | 14.44 | 1 | 0.152 |
| Oct 08 19:19 | Thu Oct 08 03:19PM | Biases, Variant A | CT Audience - Engaged Subs, excl. "Sent - Variant B" | 164,264 | 163,561 | 49,863 | 30.5% | 611 | 0.37% | 573 | 3.50 | 13 | 0.079 |
| Oct 08 18:08 | Thu Oct 08 02:08PM | Biases, Variant B | CT Audience - Engaged Subs | 164,694 | 163,904 | 31,600 | 19.3% | 509 | 0.31% | 256 | 1.56 | 9 | 0.055 |
| Oct 06 00:00 | Mon Oct 05 08:00PM | OHI: Weighty Decision | OHI Audience - Engaged Subs | 375,151 | 372,877 | 86,917 | 23.3% | 973 | 0.26% | 1,076 | 2.89 | 26 | 0.070 |
| Oct 03 14:00 | Sat Oct 03 10:00AM | Monthly Debrief, September | "Active Supporters (CT+)" + "Clearer Thinking Plus Members" | 125 | 124 | 64 | 51.6% | 5 | 4.03% | 0 | 0.00 | 0 | 0.000 |
| Sep 29 23:00 | Tue Sep 29 07:00PM | Unanswerable Questions | CT Audience - Engaged Subs | 333,177 | 331,997 | 88,110 | 26.5% | 1,088 | 0.33% | 1,109 | 3.34 | 13 | 0.039 |
| Sep 28 23:00 | Mon Sep 28 07:00PM | OHI: Emotion Questions | OHI Audience - Engaged Subs | 376,180 | 374,002 | 91,392 | 24.4% | 1,310 | 0.35% | 1,261 | 3.37 | 15 | 0.040 |
| Sep 26 15:00 | Sat Sep 26 11:00AM | Career workshop invite | "CT Audience - Engaged Subs - Open Rate > 60%" | 77,647 | 77,492 | 34,464 | 44.5% | 605 | 0.78% | 274 | 3.54 | 7 | 0.090 |
| Sep 24 22:00 | Thu Sep 24 06:00PM | Career Advice from Experts | CT Audience - Engaged Subs | 341,304 | 339,575 | 95,302 | 28.1% | 1,317 | 0.39% | 1,210 | 3.56 | 18 | 0.053 |
| Sep 21 23:00 | Mon Sep 21 07:00PM | OHI: The Unsaid Obvious | audience not pulled | 340,134 | 338,314 | 82,890 | 24.5% | 1,011 | 0.30% | 1,161 | 3.43 | 15 | 0.044 |
| Sep 18 23:00 | Fri Sep 18 07:00PM | Happiness findings | CT Audience - Engaged Subs | 336,296 | 334,659 | 102,074 | 30.5% | 1,532 | 0.46% | 1,756 | 5.25 | 23 | 0.069 |
| Sep 14 12:21 | Mon Sep 14 08:21AM | Who Attracts You, re-launch | a segment since deleted, excl. 3 segments | 232,000 | 230,892 | 13,346 | 5.8% | 711 | 0.31% | 129 | 0.56 | 1 | 0.004 |
| Sep 10 23:15 | Thu Sep 10 07:15PM | Who Attracts You, everyone else | a segment since deleted, excl. Engagement High + Perfect | 199,028 | 198,126 | 16,536 | 8.3% | 1,348 | 0.68% | 306 | 1.54 | 5 | 0.025 |
| Sep 10 23:00 | Thu Sep 10 07:00PM | Who Attracts You, 50 to 100% open rate | audience not pulled | 79,482 | 79,302 | 23,470 | 29.6% | 1,843 | 2.32% | 107 | 1.35 | 2 | 0.025 |
| Sep 09 04:02 | Wed Sep 09 12:02AM | OHI: Dating App Incentives | audience not pulled | 276,605 | 275,462 | 70,460 | 25.6% | 1,238 | 0.45% | 837 | 3.04 | 10 | 0.036 |

Totals for these 26 sends: 6,082,447 recipients, 18,342 unsubscribes, 333 spam reports. Since Oct 9 alone: 12 sends, 2,786,360 recipients, 8,287 unsubscribes, 176 spam reports.

Not in the table: 4 small sends to the career-workshop registrants (1,424 to 1,485 recipients each: reminders on Sep 30 at 10:00 and 15:51 UTC, recording on Oct 1, a second send of the recording on Oct 7; open rates 54% to 66%), an "Early Access" tool email to 130 people (Sep 7), and 15 internal test posts with 4 to 6 recipients each (see anomalies). Scheduled: "Monthly Debrief - October" for 2026-11-07 15:00 UTC.

Bounces and suppressions on the largest sends (`get_post_stats`): Steelman (Oct 22): 685 hard bounces, 5,914 soft, bounce rate 1.06%, 17,174 suppressions. Supplement wave 3 (Oct 30): 33 hard, 2,930 soft, 1.18%, 17,630 suppressions. Reason Variant A: 78 hard, 2,706 soft, 0.86%, 9,271 suppressions. Variant B: 76 hard, 2,961 soft, 0.94%, 18,460 suppressions. Biases Variant A (Oct 8, engaged only): 36 hard, 800 soft, 0.51%, 5,622 suppressions.

### Editions, grouped

| Edition | Posts | Who got it | Combined recipients | Combined unique opens | Combined verified clicks | Unsubs | Spam |
|---|---|---|---|---|---|---|---|
| Reason More Complexly (Nov 5) | 2 (Variant A and B, 2h16 apart; the variants differ in the order of the rating box, "Bad to Excellent" vs "Excellent to Bad", same subject line) | whole list, in two halves | 648,826 | 112,191 | 751 | 1,711 | 14 |
| Supplement Paradox (Oct 16 to 30) | 4 large sends + 6 test posts | wave 1 to 125.5k (Oct 16 morning), wave 2 to the engaged segment 259.4k (Oct 16 afternoon), resend to 48k non-openers with a 50%+ lifetime open rate (Oct 19), wave 3 to 252k (Oct 29 evening ET, 2.6% opened) | 685,093 | 80,249 | 1,279 | 1,354 | 61 |
| Steelman (Oct 22) | 1 + 2 test posts | whole list in one send | 624,751 | 126,355 | 3,375 | 3,457 | 80 |
| Biases (Oct 8) | 2 (Variant A and B, 71 min apart) | engaged segment in two halves | 328,958 | 81,463 | 1,120 | 829 | 22 |
| Unanswerable Questions (Sep 29) | 1 | engaged segment | 333,177 | 88,110 | 1,088 | 1,109 | 13 |
| Career Advice (Sep 24) | 1 + 1 test | engaged segment | 341,304 | 95,302 | 1,317 | 1,210 | 18 |
| Happiness (Sep 18) | 1 | engaged segment | 336,296 | 102,074 | 1,532 | 1,756 | 23 |
| Who Attracts You tool launch (Sep 7 to 14) | 4 | early access 130, then 50%+ openers 79k, everyone else 199k, re-launch 232k | 510,640 | 53,422 | 3,925 | 542 | 8 |

Key change inside the window: until Oct 8 the article went to "CT Audience - Engaged Subs" only (about 330k to 340k recipients). From Oct 16 every article has reached the whole CT audience (about 625k to 650k), either in one send (Steelman) or in waves. The non-engaged part of the list opened at 2.6% (Supplement wave 3) and produced 49 of that edition's 61 spam reports.

Recipient counts do not match the current size of the segment named on the post in several cases, and the post records show no exclusion that would explain it: "CT Audience - All Subscribers" has 666,924 members today but posts addressed to it show 125,521 (Oct 16), 252,169 (Oct 30), 324,457 and 324,369 (Nov 5 to 6) recipients; "OHI Audience - Engaged Subs" has 161,379 members today but the Sep 28, Oct 6 and Oct 21 OHI sends addressed to it had 371k to 376k recipients; "OHI Audience - All Subscribers" has 660,233 today but the Oct 14 OHI addressed to it had 358,641. See "Could not determine".

### Summary of send practice

- Cadence for a subscriber who is on both audiences and engaged: normally 2 emails a week (One Helpful Idea early in the week, the article later in the week), plus an occasional promotional email to the high-open tiers. It is not steady: no article went to engaged readers in the week of Oct 26 (only wave 3 to the non-engaged and a coaching promo), and no One Helpful Idea has gone out since Oct 20 (none in the weeks of Oct 26 and Nov 2 as of Nov 6).
- Send days and times actually used (US Eastern). Articles: Fri Sep 18 7:00pm, Thu Sep 24 6:00pm, Tue Sep 29 7:00pm, Thu Oct 8 2:08pm and 3:19pm, Fri Oct 16 8:57am and 1:12pm, Thu Oct 22 7:00pm, Thu Oct 29 8:00pm (wave 3), Thu Nov 5 5:00pm and 7:16pm. One Helpful Idea: Wed Sep 9 12:02am, Mon Sep 21 7:00pm, Mon Sep 28 7:00pm, Mon Oct 5 8:00pm, Tue Oct 13 9:51pm, Tue Oct 20 11:05pm. So Thursday evening is the modal article slot but 4 of the last 7 article sends were at other times, and One Helpful Idea has drifted from Monday 7pm to Tuesday 11pm.
- Resends: one resend to non-openers in the window (Supplement Paradox, Oct 19, 3 days after the first send, limited to people with a lifetime open rate of 50%+ who had not opened: 47,997 recipients, 18.0% opened, 80 verified clicks, 105 unsubscribes, 1 spam report). Before that, the Sep 14 "re-launch" of the Who Attracts You email (232,000 recipients, 5.8% opened).
- Subject-line A/B tests: used on most large sends through beehiiv's split test (1 hour duration, 10% to 40% of the audience as the sample, winner auto-sent to the rest). Of the 23 posts whose record I pulled, 16 had a split test configured; in 4 of those (three One Helpful Idea sends and the Sep 14 re-launch) the "variant" subject line was identical to the control, so nothing was tested. Winners are picked on tiny gaps after one hour: Steelman 3.15% vs 3.45% vs 3.66% (about 20.8k recipients per arm); Biases Variant A 8.94% vs 8.67% vs 8.91% (about 10.9k per arm).
- Manual content tests: twice (Oct 8 and Nov 5) the edition was split into two separate posts to test the order of the rating box.
- Promotional, sponsor and dedicated sends in the last 60 days (Sep 7 to Nov 6): 3 coaching promos ("Limited spots for the rest of 2026": Oct 12 to 6,583 people with a 100% open rate, Oct 14 to 18,279 and Oct 26 to 72,551 in the 50% to 99% tier; combined 97,413 recipients, 504 verified clicks, 359 unsubscribes); 1 workshop invitation (Sep 26, 77,647); 4 workshop reminder and recording emails to about 1.4k registrants; the Who Attracts You tool launch (4 sends, Sep 7 to 14). No stand-alone sponsor email exists in the post list: sponsors run as boxes inside the regular editions (per the project notes; I did not open post bodies to count them).
- The coaching promo to the 100% open-rate tier had the highest unsubscribe rate of any send in the window: 95 unsubscribes on 6,577 delivered, 14.4 per 1,000.

## 4. Per-mailbox-provider results

Source: `get_post_isp_breakdown` on 10 sends, pulled 2026-11-06 (one call by me, the rest condensed by two helper agents into `isp_breakdown_part1.md` and `isp_breakdown_part2.md` in the session scratchpad; they summed the rows by provider family). The tool lists only recipient domains with 50 or more subscribers, so each row set is a sample (about 83% to 86% of it is Gmail). Opens here include bot and scanner opens (the tool says so), which inflates Apple (Mail Privacy Protection) and some school domains. Open rate = summed opens / summed delivered. Families: Google = gmail.com + googlemail.com; Microsoft = hotmail.*, outlook.*, live.*, msn.com; Yahoo/AOL = yahoo.*, ymail.com, rocketmail.com, aol.com; Apple = icloud.com, me.com, mac.com.

| Send (UTC) | Post and audience | Google sent | Google open rate | Microsoft open rate | Yahoo/AOL open rate | Apple open rate | Google share of listed sent |
|---|---|---|---|---|---|---|---|
| Sep 29 23:00 | Unanswerable Questions, engaged segment | 238,144 | 20.33% | 52.19% | 62.36% | 93.29% | 85.1% |
| Oct 08 18:08 | Biases Variant B, engaged half (sent first) | 130,885 | 9.09% | 52.77% | 55.43% | 85.50% | 85.9% |
| Oct 08 19:19 | Biases Variant A, engaged half (sent second) | 130,404 | 22.73% | 53.77% | 56.08% | 84.03% | 85.9% |
| Oct 16 12:57 | Supplement wave 1 (sent first) | 98,377 | 5.23% | 19.48% | 30.06% | 73.76% | 85.1% |
| Oct 16 17:12 | Supplement wave 2, engaged segment | 205,920 | 12.96% | 57.64% | 56.86% | 86.77% | 85.3% |
| Oct 21 03:05 | One Helpful Idea, OHI engaged | 303,075 | 14.81% | 47.80% | 51.70% | 78.19% | 86.3% |
| Oct 22 23:00 | Steelman, whole list | 439,824 | 20.40% | 31.74% | 31.24% | 79.27% | 82.9% |
| Oct 30 00:00 | Supplement wave 3, non-engaged remainder | 194,147 | 1.03% | 14.03% | 4.28% | 22.95% | 81.4% |
| Nov 05 22:00 | Reason Variant A, whole-list half (sent first) | 254,084 | 6.48% | 20.44% | 22.56% | 58.92% | 83.4% |
| Nov 06 00:16 | Reason Variant B, whole-list half (sent second) | 253,480 | 24.84% | 16.35% | 16.97% | 56.30% | 83.3% |

Which sending address each post used: could not determine per post. The post record (`get_post`) does not expose the From address or sending domain; the publication has one email domain configured today, `ohi.clearerthinking.net` (section 5).

Gmail trend:
- Gmail is 81% to 86% of the listed volume, so the list's overall open rate is essentially its Gmail open rate.
- Gmail opens far below every other provider on the same send. On engaged-segment sends Microsoft and Yahoo/AOL open at 52% to 62% while Gmail opens at 9% to 23%.
- Against the earlier baseline in the project's Sep 2026 analysis (Gmail on the ohi domain: 34% in July easing to 26% by September, memory note `project_newsletter_send_strategy_2026_09`), Gmail on engaged-segment sends is now lower again: 20.3% (Sep 29), 13.0% (Oct 16), 14.8% (Oct 21, OHI).
- Gmail swings widely between sends that differ only in timing. Both manual A/B splits went to two halves of the same segment about 1 to 2 hours apart: Oct 8, the first half sent got 9.09% at Gmail and the second 22.73%; Nov 5, the first half got 6.48% and the second 24.84%. Microsoft, Yahoo/AOL and Apple were flat between the halves (within 4 points, and on Nov 5 slightly higher for the first half). On Oct 16 the first send of the day also got the lowest Gmail rate (5.23%). So in all three cases the first large send of the day opened at 5% to 9% at Gmail and the one after it at 13% to 25%. Cause not determined from the API; the pattern is Gmail-specific.
- Whole-list sending pulls the non-Gmail providers down by dilution (Microsoft 52% to 58% on engaged sends, 32% on the whole-list Steelman, 14% on the non-engaged remainder), and the non-engaged remainder opened at 1.03% at Gmail (1,980 opens on 192,004 delivered).

Other things visible in the provider rows:
- Eight look-alike domains (careney.com, rpaintel.com, murkstar.com, dnsink.com, mrworlds.com, lanvos.com, primetor.com, netiren.com), each with about 100 to 125 subscribers, have exactly 0 opens on every one of the four whole-list sends between Oct 22 and Nov 6 (898 to 1,624 addresses per send between them). They do not appear on the engaged-only sends. They look like disposable or bot sign-up domains that are still being mailed.
- Many school and university domains show 98% to 100% opens on some sends and ordinary rates on others (for example one large university domain: 100% on Nov 5 and 6, about 21% on Oct 21 and 22), which is the signature of security scanners opening mail, not people. Counts of rows at 98%+ with 50+ sent: 15 rows on Nov 6 Variant B, 11 on Variant A, 15 on Oct 8 Variant A.
- Proton addresses show 0.2% to 7% opens on every send (image blocking), so open-based engagement rules treat most Proton readers as inactive.
- yandex.ru bounced about half of what was sent to it on Oct 16 and Oct 21 (211 sent, 94 delivered; 210 sent, 109 delivered).

## 5. Sending setup

Sources: `get_publication`, `get_publication_settings`, `get_workspace`, `dig` run 2026-11-06 17:46 UTC (default resolver, 8.8.8.8, 1.1.1.1 and the authoritative ns1.hover.com / ns1.wix.com), and two files in this repo for history.

What beehiiv reports:
- Email (sending) domain configured on the publication: `ohi.clearerthinking.net`, status reported by beehiiv: `warming_up`. Only one email domain is attached to the publication today. beehiiv's help centre describes "Smart Warming" as automatic for every custom domain (`search_documentation`, article "Smart Warming and how it applies to you"); the tool does not say why a domain in use since at least Dec 2025 still shows `warming_up`, or what share of volume that affects.
- From address: `clearerthinking@ohi.clearerthinking.net` (recorded for the Aug 13 2026 split test in `reports/newsletter_send_strategy_2026-09-25_src/datapoints.json`; the connector does not expose the From address per post, so I could not confirm it for each recent send). Sender name: "ClearerThinking.org"; `use_post_author_name: false`.
- The older sending identity `info@clearerthinking.net` carried the main newsletter until 2026-07-01, when the main newsletter moved onto the ohi domain (same repo sources; verified claim in the brief). Monthly volume delivered from the ohi domain went from about 0.9M (June 2026) to 2.4M (July), 2.5M (August), 3.4M (September) and 2.8M (October), per `reports/ohi_open_rate_drop_2026-11-06.html`.
- Reply-to address: could not determine (not exposed by `get_publication_settings` or `get_post`).
- Branded link (click-tracking) domain: `elink7ea.clearerthinking.net`, status `live` (CNAME to `branded-link.beehiiv.com`).
- Web domain: none (the beehiiv site lives at clearerthinking.beehiiv.com). `white_labeled: true`, private branding on.
- Workspace plan: Enterprise, `max_subscriptions` 700,000. The publication has 678,349 active subscribers, 96.9% of that ceiling (21,651 left; at the current net growth of about 28k per 4 weeks that is roughly three weeks, assuming the cap counts active subscribers in this publication only, which the tool does not state; the workspace also holds three small sister publications).
- Dedicated IP: could not determine (no tool exposes IP configuration).
- Publication time zone: Eastern Time (US and Canada).

### DNS (raw records)

| Name | Type | Record |
|---|---|---|
| clearerthinking.net | TXT (SPF) | `v=spf1 include:_spf.hostedemail.com include:hover.com include:servers.mcsv.net include:mailgun.org ~all` |
| clearerthinking.net | MX | `10 mx.hover.com.cust.hostedemail.com.` |
| _dmarc.clearerthinking.net | TXT | `v=DMARC1; p=quarantine;` (no `sp=`, no `rua=`, no `ruf=`, no `pct=`) |
| default._bimi.clearerthinking.net | TXT | none |
| s1._domainkey.clearerthinking.net, s2._domainkey.clearerthinking.net | CNAME | `s1.domainkey.u45518438.wl189.sendgrid.net.`, `s2.domainkey.u45518438.wl189.sendgrid.net.` (SendGrid DKIM, the infrastructure beehiiv sends through) |
| k2._domainkey.clearerthinking.net, k3._domainkey.clearerthinking.net | CNAME | `dkim2.mcsv.net.`, `dkim3.mcsv.net.` (Mailchimp DKIM, left from the previous platform) |
| ohi.clearerthinking.net | TXT, MX, CNAME, NS | none of its own. It answers only through a wildcard A record on the zone (`*.clearerthinking.net` A `216.40.34.41`, TTL 900) |
| _dmarc.ohi.clearerthinking.net | TXT | none (only the wildcard A), so receivers fall back to the organisational record `p=quarantine` |
| s1._domainkey.ohi.clearerthinking.net, s2._domainkey.ohi.clearerthinking.net | CNAME / TXT | none (only the wildcard A) |
| default._bimi.ohi.clearerthinking.net | TXT | none |
| elink7ea.clearerthinking.net | CNAME | `branded-link.beehiiv.com.` |
| clearerthinking.org | TXT (SPF) | `v=spf1 include:_spf.hostedemail.com include:hover.com include:servers.mcsv.net ~all` (plus ahrefs, facebook, prowly and google verification strings) |
| clearerthinking.org | MX | `10 mx.hover.com.cust.hostedemail.com.` |
| _dmarc.clearerthinking.org | TXT | `v=DMARC1; p=none;` (no `rua=`) |
| default._bimi.clearerthinking.org | TXT | none |
| s1._domainkey.clearerthinking.org, s2._domainkey.clearerthinking.org | CNAME | chain through `...s018.ascendbywix.com.` to `s1.domainkey.u55926038.wl039.sendgrid.net.` / `s2...` (Wix's SendGrid account, not beehiiv's) |
| k1, k2, k3._domainkey.clearerthinking.org | CNAME | `dkim.mcsv.net.`, `dkim2.mcsv.net.`, `dkim3.mcsv.net.` (Mailchimp) |
| Nameservers | NS | clearerthinking.net: ns1/ns2.hover.com; clearerthinking.org: ns1/ns2.wix.com |

Reading of the DNS, limited to what the records show:
- The newsletter's DKIM lives at the root `clearerthinking.net` (SendGrid selectors s1 and s2). The sending subdomain `ohi.clearerthinking.net` has no SPF, DKIM, DMARC or MX record of its own; mail from `clearerthinking@ohi.clearerthinking.net` can still pass DMARC through relaxed alignment with the root domain's DKIM. `reports/ohi_open_rate_drop_2026-11-06.html` checked headers of delivered copies (Aug 5, Aug 26, Oct 21) and found SPF and DKIM passing and one-click unsubscribe present.
- DMARC: `p=quarantine` on .net and `p=none` on .org, and neither has a `rua=` reporting address, so nobody receives DMARC aggregate reports.
- No MX on `ohi.clearerthinking.net`: a reply typed to the From address has no mail server to go to unless a different reply-to is set (could not determine the reply-to).
- No BIMI record on any of the three names.
- The .net SPF still authorises Mailchimp (`servers.mcsv.net`) and Mailgun (`mailgun.org`), and Mailchimp DKIM keys are still published on both domains, although the list moved to beehiiv in 2025.
- The wildcard A record makes every made-up subdomain of clearerthinking.net resolve, which hides missing records from simple checks.
- Whether the domain is registered in Google Postmaster Tools: could not determine from DNS (the root has one `google-site-verification` TXT; that string is used for several Google products).

## 6. Sign-up and opt-in

Sources: `get_publication_settings`, `get_opt_in_email`, `list_subscribe_forms`, `list_signup_flows`, `list_custom_fields`, `list_tags`, `list_newsletter_lists`.

- Double opt-in: OFF (`double_opt_in: false`). A confirmation email template exists ("Confirm your Clearer Thinking subscription", `get_opt_in_email`) but is not in use.
- Smart nudge (beehiiv's reminder to unconfirmed subscribers): off (`smart_nudge: false`).
- `require_subscriber_approval: false`; `allow_subscription_pauses: false` (a reader cannot pause instead of unsubscribing).
- How people actually get on the list: 97% of new subscribers in the last 4 weeks arrived through the API from CT's own tools (37,992 of the 39,074 still active; section 1), not through a beehiiv form. So beehiiv's form-level protections do not apply to most sign-ups; whatever validation exists lives in the tools' own code (GuidedTrack programs calling the beehiiv API), which this audit did not inspect.
- Subscribe forms (7, all beehiiv "v2" inline forms): "Clearer Thinking - Subscribe" and "One Helpful Idea - Subscribe" (Dec 2025; the OHI form has unpublished draft changes), "Critical Thinking Challenge", "Decision Making Challenge", "Best of CT For Youtube Viewers", "Meditation Website" (all Dec 2025), "Workshop - Spencer's #1 Self-Help" (May 2026). The embed channel accounts for 1,154 active subscribers in total.
- Signup flows (1): "Recommendations Flow", the default; after signing up on the beehiiv page a new subscriber is shown the recommendations modal. No survey, preference or welcome step.
- Bot protection or email validation: nothing is exposed by the settings tools (no captcha, validation or throttling setting is returned), so could not determine. Indirect evidence that junk gets in: beehiiv itself created a segment of 772 "Subscribers using disposable/throwaway domains" on 2026-02-19 that was never actioned (section 8), and eight look-alike domains with zero opens are still being mailed (section 4).
- Preference lists: none. `list_newsletter_lists` (archived included) returns 0, so beehiiv's native newsletter lists / preference centre is not used.
- What stands in for preferences: two boolean custom fields created 2025-08-20, `clearerthinking.org` ("ClearerThinking.org") and `one_helpful_idea` ("One Helpful Idea"). Every send audience is built on them: "CT Audience - All Subscribers" (666,924) requires the first to be true, "OHI Audience - All Subscribers" (660,233) the second. 19,892 active subscribers have both set to false and receive neither newsletter (segment "Not OHI or CT Audience But Subscribed", last processed 2026-10-22). Whether a reader can change these two flags on their own (a manage-preferences page) could not be determined from the connector. There is no flag for events, promotions or sponsor emails, so a reader cannot opt out of coaching promos or workshop invitations while staying on the newsletter.
- Custom fields (35). Grouped by use:
  - Audience flags: `clearerthinking.org`, `one_helpful_idea`, `podcast`, `dating_app_updates`, `email_test_group`.
  - Tool history: `last_tool_tried`, `first_tool_tried` (never populated, per the project memory note), `tools_tried_(pipe_separated)`, `tools_tried_(deprecated)` (a 95-option list), `tags_(comma_separated)`.
  - Acquisition: `utm_sources_(comma_separated)`, `utm_media_(comma_separated)`, `utm_campaigns_(comma_separated)` (multi-touch), `subsource`, `mla_tags_(comma_separated)`, `leaf`, `bluedot_subs`.
  - Purchases and membership: `personality_test_pdf_purchase`, `cognitive_assessment_purchase`, `clearer_thinking_plus_tier` and `supporter_tier` (two list fields with the same three options: Supporter, Explorer, Navigator).
  - Events and programmes: `7_day_critical_thinking_challenge`, `7_day_decision_making_challenge`, `disagreement_workshop_sign_ups_(2025)`, `form_new_habits_workshop`, `meditation`, `beta_testers`, `beta_tester_interviews`.
  - Feedback: `newsletter_rating`, `newsletter_rating___open_question`.
  - Migration: `all_unsubs_from_mailchimp` (boolean, created 2025-11-13).
  - Identity: `first_name`, `last_name`, `company`. Leftover: `any_arbitrary_text_value`.
- Tags (4): `attractiveness-study` (192,989 subscribers), `dating_app` (72,910), `career_workshop_sep2026` (1,509), `unanswered_outreach` (11).

## 7. Automations

Sources: `list_automations` (18 automations: 8 live, 9 inactive, 1 draft; a second call filtered on the `unengaged` trigger returned 0), `get_automation` and `get_automation_stats` for the New Subscribers drip, the Sunset Campaign, Dating App Updates and the CT+ welcome series. For the other 14 only the list-level figures were pulled (trigger type, enrolled count, average open rate); their steps were not read.

| Automation | State | Trigger | Emails | Enrolled all time | In progress | Avg open rate | Class |
|---|---|---|---|---|---|---|---|
| [Drip Campaign] New Subscribers | live (republished 2026-10-28) | every signup, no conditions | 4 | 119,302 | 45,673 | 27.1% | welcome/onboarding (in practice mostly coaching sales) |
| [Drip Campaign] Dating App Updates | live (2026-10-22) | entering segment "[Drip Campaign] Dating App Updates" | 1 | 31,156 | 0 | 18.7% | other (product update) |
| Decision Making Crash Course | live | signup | not read | 834 | 0 | 44.4% | other (email course) |
| [Drip Campaign] Welcome Email To Clearer Thinking Plus | live (2026-09-28) | entering segment "Clearer Thinking Plus Members" | 5 (welcome, coaching testimonials, 3 tier-specific check-ins) | 179 | 26 | 66.7% | paid-member onboarding |
| Bonus To Youtube Viewers | live | signup | not read | 154 | 0 | 48.1% | other (lead magnet) |
| New Subscribers (Meditation Form) | live (2025-12-27) | signup | not read | 116 | 0 | 0.0% | other |
| Critical Thinking Crash Course | live | signup, manual | not read | 73 | 3 | 34.8% | other (email course) |
| [Drip Campaign] Cognitive Assessment Purchases | live (2026-09-22) | segment action | not read | 68 | 0 | 38.2% | other (post-purchase) |
| [Drip Campaign] Tried Personality Test | inactive (last edit 2026-09-22) | segment action | not read | 25,796 | 0 | 39.9% | drip by tool |
| [Drip Campaign] Tried Rationality Test | inactive (2026-09-22) | segment action | not read | 14,377 | 0 | 19.6% | drip by tool |
| [Drip Campaign] Tried Unique Traits Test | inactive (2026-08-12) | segment action | not read | 4,139 | 0 | 15.2% | drip by tool |
| [Drip Campaign] Tried Intrinsic Values Test | inactive (2026-08-12) | segment action | not read | 4,125 | 0 | 29.3% | drip by tool |
| [Drip Campaign] Tried Philosophical Beliefs | inactive (2026-08-12) | segment action | not read | 4,125 | 0 | 16.8% | drip by tool |
| [Drip Campaign] Tried Worth of Your Time Calculator | inactive (2026-08-12) | segment action | not read | 4,112 | 0 | 17.1% | drip by tool |
| [Drip Campaign] Sunset Campaign | inactive (last edit 2026-06-26) | entering segment "[Drip Campaign] Disengaged Subscribers" | 2 | 2,169 completed (first email sent to 21,646) | 0 | 1.5% | sunset/cleanup |
| [Drip Campaign] Tried Imposter Syndrome Tool | inactive (2026-09-22) | segment action | not read | 412 | 0 | 28.4% | drip by tool |
| Workshop - Spencer's #1 Self-Help | inactive | signup, manual | not read | 56 | 0 | 10.9% | event/workshop |
| Josh's Test Automation (Please Ignore!) | draft | manual | 0 | 0 | 0 | 0 | test |

### The New Subscribers drip, step by step (`get_automation`, live workspace)

| Day after sign-up | Step |
|---|---|
| 0 | Sets both audience flags to false (`one_helpful_idea` = false, `clearerthinking.org` = false), so a new subscriber is on neither newsletter. No email is sent by this automation at sign-up. |
| 1 | Email "Big news" (preview: "Get matched with a life coach who aligns with your personality and goals."): a coaching offer is the first automation email a new subscriber receives. |
| 7 | Sets both audience flags to true: the subscriber joins both the main newsletter and One Helpful Idea. (The send segments also require `signup_date <= NOW() - 1 week`.) |
| 14 | Email "Does IQ actually matter?" |
| 28 | Email "Should you have a life coach?" |
| 42 | Branch on a subscriber tag (tag id not among the 4 tags that exist today); the "yes" arm gets "You can help advance psychology research". 2,672 went "yes", 60,153 "no". |

Per-email results (`get_automation_stats`):

| Email | All time: sent | All time: open rate | All time: spam rate | Last 4 weeks: sent | Last 4 weeks: open rate |
|---|---|---|---|---|---|
| Big news (day 1) | 111,605 | 29.27% | 0.03% | 41,261 | 33.36% |
| Does IQ actually matter? (day 14) | 113,747 | 25.55% | 0.01% | 37,992 | 25.57% |
| Should you have a life coach? (day 28) | 82,163 | 22.71% | 0.01% | 29,539 | 20.40% |
| You can help advance psychology research (day 42, tagged only) | 2,656 | 59.65% | 0.00% | not listed | not listed |

So from automations alone a new subscriber gets 1 email in the first 7 days (the coaching offer) and 3 in the first 30 days (two of the three are about coaching), and starts receiving the newsletters on day 7. Whether beehiiv's built-in welcome email (a publication setting, separate from automations) is switched on could not be determined: the settings tool does not return it. Unsubscribe rates per automation email: see the line added below once pulled; the project memory note of 2026-10-28 recorded 1.34% unsubscribes per send for "Big news" against 0.21% to 0.26% for the other drip emails.

### Sunset and win-back

- No win-back or re-engagement automation is live. No automation uses beehiiv's `unengaged` trigger.
- One sunset flow exists and is switched off: "[Drip Campaign] Sunset Campaign". Published 2026-06-18, last enrolment 2026-06-26, last edited 2026-06-26, state inactive. Trigger: entering the segment "[Drip Campaign] Disengaged Subscribers" (126,284 members, segment status "failed"). Steps: email "Do you still want to hear from us?"; wait 7 days; if no click in the last 10 days, email "We're going to stop emailing you"; wait 10 days; if no open in the last 10 days, set the subscription to inactive; exit.
- What it did in its 8 days (`get_automation_stats`, all time): first email sent to 21,646 (delivered 21,131, 1.83% opened), second to 19,296 (delivered 18,851, 1.19% opened). At the final "set inactive" step the counts are 11 completed and 2,678 recorded as unsubscribed; the 10-day wait before it shows 615 completed and 16,735 failed, which is what you would see if the automation was switched off while most people were still waiting. So about 21.6k of the roughly 126k disengaged subscribers were warned, and at most a few thousand were actually removed. The exact number deactivated by the flow could not be determined from these counts.
- The six per-tool drips built on 2026-08-11 (plus the Imposter Syndrome one) are all inactive; since Sep 22 every tool sign-up gets the same generic New Subscribers drip. The copy for a version personalised by `last_tool_tried` exists in the repo (`reports/welcome_drip_copy_2026-10-28_src/`) but the live automation has no branch on that field.
- Paid-member onboarding: live ("Welcome Email To Clearer Thinking Plus": welcome email at once, coaching testimonials after 2 days, a tier-specific check-in after a further 21 days; 179 enrolled, 66.7% average open rate).

## 8. Hygiene evidence

PENDING.

## 9. Reader feedback and preferences

Sources: `list_polls`, `list_surveys`, `get_referral_program`, `list_recommendations` (outgoing and incoming), `list_tiers`, `get_publication_stats`.

- Polls: 1, a draft never published ("Welcome Survey": "Which best describes you right now?", created 2026-06-23). No beehiiv poll has ever run.
- Surveys: 1, a draft with 0 responses ("Help us improve by rating this newsletter", created 2026-01-09). Article ratings are collected outside beehiiv, through a GuidedTrack program linked from each edition (project CLAUDE.md: program 38551, with a separate ratings dashboard); the two `newsletter_rating` custom fields exist in beehiiv, how full they are was not checked.
- No welcome survey or preference question is asked at sign-up (the only signup flow step is the recommendations modal).
- Referral program: `enabled: true` but 0 milestones and no rewards configured, so it is switched on and empty. The referral channel accounts for 3 active subscribers all time.
- Recommendations, outgoing (CT recommending others): 23 records, 6 active (4 free, 2 paid boosts at $2.00 per lead), 20 subscribers driven all time, $1.60 earned.
- Recommendations, incoming (others recommending CT): 83 records, 67 actively recommending, 599 subscribers gained all time, all free, $0 spent. The largest sources on the first page of results: The How to Live Newsletter (94), vocab with ease (44), The Stoic Systems Thinker (17). CT buys no paid boosts.
- Paid tiers on beehiiv: 1 active tier, "Supporter" at $9.00 a month, created 2026-10-06 (the same day as two "Monthly Debrief - Testing Paywall" test posts, one of which recorded 1 upgrade). CT+ memberships (Supporter, Explorer, Navigator) are otherwise sold through Stripe and mirrored into beehiiv as custom fields and segments ("Clearer Thinking Plus Members" 161, "Active Supporters" 102). The monthly members email goes to those segments (125 recipients on Oct 3).
- beehiiv earnings shown by `get_publication_stats`: $1,307.01 all time, $202.50 in the last 4 weeks (the tool does not break this down).

## Could not determine

PENDING.

## Anomalies

PENDING.
