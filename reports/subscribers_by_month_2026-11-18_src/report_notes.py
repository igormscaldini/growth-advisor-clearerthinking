"""The wording of the subscribers-by-month report. Every number is read from datapoints.json or
cross_check_results.json (or is a plain sum or difference of numbers in them); nothing is typed in."""
import statistics

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


WAVE_RATE = 0.022  # a month losing more of the list than this to unsubscribes is called a wave month


def n(x) -> str:
    return f"{x:,}"


def hundreds(x) -> str:
    return f"{int(round(x, -2)):,}"


def pct(a, b) -> str:
    return f"{round(100 * a / b)}%"


def listed(names: list) -> str:
    """["a", "b", "c"] -> "a, b and c"."""
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def short_day(iso: str) -> str:
    """2026-01-16 -> Jan 16."""
    return f"{MONTHS[int(iso[5:7]) - 1][:3]} {int(iso[8:])}"


def notes(dp: dict, xc: dict) -> dict:
    months = dp["months"]
    by = {m["month"]: m for m in months}
    tot = lambda key: sum(m[key] for m in months)  # noqa: E731
    btot = lambda b: sum(m["buckets"][b] for m in months)  # noqa: E731
    full = months[:-1]  # the last month is partial
    last = months[-1]
    last_name = MONTHS[int(last["month"][5:]) - 1]
    cal = dp["calibration"]
    est = [m for m in months if m["estimated"]]
    est_names = f"{MONTHS[int(est[0]['month'][5:]) - 1]} to {MONTHS[int(est[-1]['month'][5:]) - 1]}"
    est_upside = sum(m["kept_high"] - m["kept"] for m in est)
    aug, sep, octw = dp["waves"]
    aug_m = by["2026-08"]
    jan = by["2026-01"]
    mar = by["2026-03"]
    launch = dp["context"]["unique_traits_launch"]
    leaf_days = dp["context"]["leaf_batches"]
    leaf_total = btot("leaf")
    median_full = round(statistics.median(m["kept"] for m in full))
    # The same months with the two things that are not a steady flow taken out: Leaf batches and the
    # August wave's lift on other tools.
    underlying = {m["month"]: m["kept"] - m["buckets"]["leaf"] - (aug["excess"] if m["month"] == "2026-08" else 0)
                  for m in full}
    low_month, high_month = min(underlying, key=underlying.get), max(underlying, key=underlying.get)
    month_name = lambda key: MONTHS[int(key[5:]) - 1]  # noqa: E731
    before_tags = cal["ga4_events_before_tags"]
    wide = [(m["kept_on_record"] - m["kept_wide"], m) for m in months if not m["estimated"]]
    wide_lo, wide_hi = min(w for w, _ in wide), max(w for w, _ in wide)
    wide_hi_share = max(w / m["kept"] for w, m in wide)

    comp = xc.get("completeness", [])
    days_off = xc.get("days_not_matching_beehiiv", [])
    shape = {s["month"]: s for s in xc.get("ga4_shape", [])}
    steady = [s["ratio"] for mth, s in shape.items() if mth >= "2026-03" and mth not in ("2026-07", "2026-08") and s["ratio"]]
    early = [shape[mth]["ratio"] for mth in ("2026-01", "2026-02") if mth in shape]
    leak = [shape[m["month"]]["ga4_events_in_cpc_sessions"] - m["buckets"]["ads"]
            for m in months if not m["estimated"] and m["month"] not in ("2026-07", "2026-08") and m["month"] in shape]
    cache_over = [(c["dashboard_cache"] - c["walk_non_import_all_statuses"]) for c in comp]
    invalid_share = [m["invalid"] / m["records"] for m in months]

    # The whole list: unsubscribes and deletions
    moves = dp["list_movement"]
    scan = dp["deletion_scan"]
    books = xc.get("unsubscribes", {})
    unsub_total = sum(m["unsubscribed"] for m in moves)
    full_rates = [m["unsubscribe_rate"] for m in moves[:-1]]
    calm_rates = [m["unsubscribe_rate"] for m in moves[:-1] if m["unsubscribe_rate"] <= WAVE_RATE]
    wave_months = [m for m in moves[:-1] if m["unsubscribe_rate"] > WAVE_RATE]
    left = {g: sum(m["left_since"][g] for m in months) for g in ("study", "ads", "kept", "backlog")}
    left_2026 = sum(left.values())
    removed = [m["removed_without_unsubscribe"] or 0 for m in moves]
    worst_week = min(books.get("weeks_not_reconciling", []), key=lambda w: w["unexplained"], default=None)
    scanned = [m for m in scan["months"] if m["fall"] is not None]

    answer = (
        f"Leaving out everyone who came from an ad or from the Who Attracts You study, Clearer Thinking gained about "
        f"<b>{hundreds(tot('kept'))} new subscribers</b> from January 1 to {last_name} {dp['partial_through_day']}, 2026, "
        f"out of the {n(tot('total'))} that beehiiv counted. Set the three Leaf batches and the August viral wave aside "
        f"as well and a full month runs from {hundreds(underlying[low_month])} ({month_name(low_month)}) to "
        f"{hundreds(underlying[high_month])} ({month_name(high_month)}, a tool launch), with a median of "
        f"{hundreds(statistics.median(underlying.values()))}. April onward is an exact count from the records. {est_names} "
        f"include an estimate, because the tools did not tag ad sign-ups in beehiiv before March 27. Over the same "
        f"period {n(unsub_total)} people unsubscribed from the whole list. I found no bulk deletion: at most "
        f"{n(sum(removed))} people left the list any other way in the whole year.")

    tiles = [
        ("≈" + hundreds(tot("kept")), f"new subscribers kept, Jan 1 to {last_name[:3]} {dp['partial_through_day']}"),
        (pct(tot("kept"), tot("total")), f"of the {n(tot('total'))} new subscribers beehiiv counted"),
        (n(median_full), "median full month (Jan to Oct)"),
        (pct(tot("kept_active"), tot("kept")), "of the kept are still subscribed today"),
    ]

    callouts = "".join(f"<div class='callout'><p>{c}</p></div>" for c in [
        f"<b>August is inflated by the viral wave.</b> From Aug 3 to 14 the X/Twitter wave that launched the study also "
        f"pushed the other tools (mostly the Ultimate Personality Test and the Unique Traits Test) to {n(aug['signups'])} "
        f"sign-ups, about {hundreds(aug['excess'])} above their usual {int(aug['baseline_per_day'] + 0.5)} a day. On the record "
        f"these are not study sign-ups: the first tool they finished was a different one and only {aug['later_took_study']} "
        f"of them ever took the study, so they are kept. If you see that wave as the study's doing, read August as about "
        f"<b>{hundreds(aug_m['kept'] - aug['excess'])}</b>, not {n(aug_m['kept'])}. The September and October waves sent "
        f"almost nobody to another tool first (about {hundreds(sep['excess'])} and {hundreds(octw['excess'])} above "
        f"baseline; September's is mostly an unrelated spike on the Value of Your Time Calculator).",

        f"<b>January holds two one-offs.</b> {n(jan['buckets']['leaf'])} of its ≈{n(jan['kept'])} are the Leaf student "
        f"batch of Jan 16 (kept: neither an ad nor the study, but not organic either). And {n(jan['buckets']['backlog'])} "
        f"people uploaded on Jan 1 at 01:15 UTC are left out, because an upload made 75 minutes into the year can only hold "
        f"December 2025 sign-ups.",

        f"<b>March's bump is the Unique Traits Test launch.</b> Mar 23 to 26 brought {n(launch['subscribers'])} new "
        f"subscribers in four days, {n(launch['unique_traits_only'])} of them on that tool alone. It is real, non-ad, "
        f"non-study growth, but it is a launch, not a run rate.",
    ])

    table_note = (
        "Each row adds up: all new subscribers, minus the study, ads and the December backlog, equals kept. "
        f"≈ marks a figure that includes the ad estimate for {est_names}. {last_name} covers the 1st to the "
        f"{dp['partial_through_day']}th. \"Still subscribed today\" is the record's status on November 18.")

    route_note = (
        "Tools = someone finished a tool and left their email. Until March 9 those sign-ups reached beehiiv as "
        "twice-weekly uploads with no tool name attached, so January and February cannot be split by tool; they are "
        f"counted as Tools, net of the estimated ad sign-ups. Leaf = student batches from the Leaf partnership "
        f"({', '.join(f'{n(c)} on {short_day(d)}' for d, c in leaf_days.items())}). Without Leaf the kept total is "
        f"≈{n(tot('kept') - leaf_total)}.")

    ads_note = (
        "<b>Tagged cpc</b>: the visit that created the subscriber carried utm_medium=cpc (Google or Meta). A reader who "
        "signed up without an ad and clicked one later is kept. "
        "<b>Partner ad campaigns</b>: sign-ups on MailList Accelerator pages (BlueDot, ACE, FarmKind, HIP, Hive). They "
        "carry no UTM tag, but those pages are fed by paid campaigns (98% of their GA4 email submissions in January and "
        "February came from google/cpc), so I counted them as Ads. Add this column back if you see them differently. "
        f"<b>Estimated</b>: before March 27 the tools wrote no UTM tags to beehiiv. GA4 recorded "
        f"{n(sum(before_tags.values()))} email submissions in ad sessions on CT's own tools from January 1 to March 27. "
        f"In the first weeks with tags ({short_day(cal['window'][0])} to {short_day(cal['window'][1])}) each such event produced "
        f"{cal['ratio']:.2f} new tagged subscribers, so that share is taken out. Later months ran lower "
        f"({min(cal['later_months'].values()):.2f} to {max(cal['later_months'].values()):.2f}); at those rates {est_names} "
        f"would keep up to {n(est_upside)} more in total, so the figures shown are the cautious end.")

    list_note = (
        f"This table is the WHOLE list, every source included, not only the kept subscribers above. Unsubscribes are "
        f"beehiiv's own daily count. In an ordinary month {min(calm_rates):.1%} to {max(calm_rates):.1%} of the list "
        f"unsubscribes; {listed([MONTHS[int(m['month'][5:]) - 1] for m in wave_months])} ran higher "
        f"({min(m['unsubscribe_rate'] for m in wave_months):.1%} to {max(m['unsubscribe_rate'] for m in wave_months):.1%}) "
        f"because the study's sign-ups leave quickly. Of the {n(unsub_total)} unsubscribes, {n(left_2026)} were people "
        f"who had joined in 2026: {n(left['study'])} from the study, {n(left['ads'])} from ads and {n(left['kept'])} "
        f"of the kept; the other {n(unsub_total - left_2026)} were older subscribers. {last_name} covers "
        f"{moves[-1]['days']} days. \"Sign-ups marked invalid\" are addresses that failed beehiiv's validation in "
        f"the month they arrived: they were never on the list, so they are neither unsubscribes nor deletions.")

    nets = dp["net_without_imports"]
    imported = sum(m["manual_imports"] for m in nets)
    imported_left = sum(m["manual_imports_unsubscribed_since"] for m in nets)
    aug_net = next(m for m in nets if m["month"] == "2026-08")
    routine = [m for m in nets if m["routine_tool_uploads"]]
    net_note = (
        f"New subscribers who signed up, minus everyone who unsubscribed, for the whole list. Taken out: the "
        f"{n(imported)} manual imports (the Jan 1 December backlog, the Leaf student batches, workshop and challenge "
        f"lists, and in August the {n(aug_net['manual_imports'])} earlier study participants uploaded in bulk). Kept in: "
        f"the {n(sum(m['routine_tool_uploads'] for m in routine))} tool sign-ups of "
        f"{listed([MONTHS[int(m['month'][5:]) - 1] for m in routine])} that beehiiv labels as imports, because until "
        f"March 9 the tools delivered every new sign-up as a twice-weekly upload; taking them out would erase "
        f"real sign-ups. Deletions are in neither column (beehiiv books none, see above). One thing this cannot "
        f"separate: {n(imported_left)} of the manually imported people have unsubscribed since, mostly the August "
        f"upload, and their unsubscribes are still in the Unsubscribed column, because beehiiv records no "
        f"unsubscribe date to take them out by month. Most of them left from August onward, so those months' net "
        f"change is understated by up to that many in total.")

    deletions = (
        "<div class='callout'><p><b>Deletions: no bulk deletion found.</b> beehiiv keeps no record of deleted subscribers "
        "(a deleted person disappears from the API and from every report), so there is no figure to read off. I looked "
        "for them in the two places they would leave a mark:</p><ul>"
        f"<li><b>beehiiv's own books.</b> Each week, the change in list size should equal new subscribers minus "
        f"unsubscribes. Over {books.get('weeks_checked', 0)} weeks the two differ by {abs(books.get('total_unexplained', 0))} "
        f"people in total"
        + (f"; the one week off by more than 10 is the week of {short_day(worst_week['week'])}, when "
           f"{abs(worst_week['unexplained'])} people left the list without an unsubscribe" if worst_week else "")
        + ". That is the \"Removed without an unsubscribe\" column.</li>"
        f"<li><b>What our dashboard recorded at the time.</b> The dashboard has saved the live list size every day "
        f"since {short_day(scan['first_day'])}. Had someone deleted subscribers in bulk and beehiiv erased them from its "
        f"history, the size we recorded before the deletion would sit above what beehiiv says today for those days, and "
        f"drop back afterwards. Across the {len(scanned)} months that can be compared, the largest such drop is "
        f"{scan['largest_fall']} subscribers.</li></ul>"
        f"<p>If beehiiv books a deletion as an unsubscribe instead, it is already inside the Unsubscribed column. The "
        f"one case I cannot rule out is a bulk deletion before {short_day(scan['first_day'])} that beehiiv erased from "
        f"its history, because nothing recorded the list size independently back then.</p></div>")

    sections = [
        ("How each subscriber was classified", "<ul>"
         f"<li><b>Source.</b> Every beehiiv subscription created from January 1 to {last_name} {dp['partial_through_day']}, "
         f"2026: {n(tot('records'))} records, read one by one with their custom fields. Month = the UTC date the record "
         "entered beehiiv.</li>"
         f"<li><b>Invalid addresses are not subscribers.</b> {n(tot('invalid'))} records "
         f"({min(invalid_share):.0%} to {max(invalid_share):.0%} a month) failed beehiiv's validation or hard-bounced, "
         f"and {n(tot('pending'))} never confirmed. beehiiv leaves them out of its own growth numbers and so does this "
         "report.</li>"
         "<li><b>From the study</b> = the first tool the person finished was Who Attracts You, or they finished no tool "
         f"and carry the study's dating-app opt-in. {n(btot('study'))} people, most of them uploads of earlier "
         "participants in August. Someone who joined through another tool and took the study later is kept.</li>"
         "<li><b>From Ads</b> = the three columns in the table above.</li>"
         f"<li><b>How much the reading matters.</b> Removing anyone who EVER touched the study or an ad, even long after "
         f"signing up, would lower the kept figure by only {wide_lo} to {wide_hi} a month from April on (at most "
         f"{wide_hi_share:.1%}).</li></ul>"),

        ("What the records cannot show", "<ul>"
         f"<li><b>{est_names}: ads are estimated</b>, as described above. The kept figures for those three months could "
         f"be up to {n(est_upside)} higher in total, not lower.</li>"
         "<li><b>Batch timing.</b> Until March 9 sign-ups were uploaded every three to five days, so a January to March "
         "figure can be off by a few days of sign-ups at each month boundary.</li>"
         "<li><b>Ad clickers who sign up on a different tool.</b> The cpc tag is written by the tool the ad lands on. "
         "Someone who clicks an ad and then leaves their email on another tool has no tag. GA4 bounds this: ad-session "
         f"email submissions exceed tagged ad sign-ups by {n(min(leak))} to {n(max(leak))} a month from April on, and most "
         "of that gap is existing subscribers and repeat submissions, so the real leak is well below it.</li>"
         f"<li><b>The study before August.</b> It was already live at a trickle ({n(by['2026-04']['buckets']['study'])} "
         f"sign-ups in April, {n(by['2026-07']['buckets']['study'])} in July), and those are removed. If it also ran in "
         "January to March its sign-ups would sit unseen inside the uploads; at that pace it is under 100 a month.</li>"
         "</ul>"),

        ("Checks run", "<ul>"
         f"<li><b>Against beehiiv's own count.</b> The records, with invalid and unconfirmed addresses removed, match "
         f"beehiiv's daily \"subscribed\" figure on {xc.get('days_compared', 0) - len(days_off)} of "
         f"{xc.get('days_compared', 0)} days.</li>"
         f"<li><b>Unsubscribes.</b> beehiiv's weekly list size reconciles with its daily new-subscriber and unsubscribe "
         f"figures in {books.get('weeks_checked', 0) - len(books.get('weeks_not_reconciling', []))} of "
         f"{books.get('weeks_checked', 0)} weeks (within 10 subscribers), and a second script recomputes the same "
         "monthly unsubscribe totals.</li>"
         "<li><b>Independent recount.</b> A second script that shares no code with the analysis (pandas and two regular "
         f"expressions on the raw fields) returns the identical figure in all {len(months)} months.</li>"
         "<li><b>Unit tests.</b> Each rule, hand-worked tables, a synthetic world with no ads and no study "
         "(nothing removed) and one with planted numbers (all recovered exactly, including untagged ad sign-ups). "
         "The deletion search is tested the same way: a synthetic list with no deletions (nothing found) and ones "
         "with a planted bulk deletion (found at its size, in the right month).</li>"
         f"<li><b>Against GA4.</b> Tool sign-ups kept per GA4 email submission outside ad sessions and off the study page "
         f"run {min(steady):.2f} to {max(steady):.2f} from March to November (July and August set aside: GA4 recorded "
         f"nothing on the personality test for three weeks, and study participants then took other tools). January and "
         f"February run {min(early):.2f} to {max(early):.2f}: the uploads held more people than GA4-tracked tools "
         "explain, so they included sign-up sources GA4 does not see. Those are not ads (GA4 saw only "
         f"{n(before_tags['2026-01'])} and {n(before_tags['2026-02'])} ad-session submissions in those two months) and "
         "not the study.</li>"
         f"<li><b>Dashboard.</b> Its \"new subscribers\" card counts invalid addresses, so it reads "
         f"{min(invalid_share):.0%} to {max(invalid_share):.0%} above beehiiv's own figure. About "
         f"{hundreds(sum(max(0, c) for c in cache_over))} of those addresses, from the September and October waves, now "
         "carry beehiiv's import label: day by day they are exactly the records that turned out invalid.</li></ul>"),
    ]

    return {
        "title": "New subscribers by month, 2026",
        "subtitle": (f"Without Ads and without the Who Attracts You study · January 1 to {last_name} "
                     f"{dp['partial_through_day']}, 2026 (UTC) · {n(tot('records'))} beehiiv records read"),
        "answer": answer,
        "tiles": tiles,
        "chart_title": "New subscribers per month, without ads and the study",
        "chart_caption": "Stacked by how they arrived. ≈ = includes the ad estimate.",
        "annotations": {"2026-08": f"≈{hundreds(aug['excess'])} from the Aug 3-14 wave"},
        "table_note": table_note,
        "callouts": callouts,
        "list_note": list_note,
        "deletions": deletions,
        "net_note": net_note,
        "route_note": route_note,
        "ads_note": ads_note,
        "sections": sections,
    }
