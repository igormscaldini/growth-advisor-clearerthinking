"""New beehiiv subscribers per month in 2026, with Ads and the Who Attracts You study taken out.

    .venv/bin/python reports/subscribers_by_month_2026-11-18_src/analysis.py

Reads data/subscriptions.jsonl (fetch_data.py) and cross_checks.json (fetch_cross_checks.py), writes
datapoints.json. Every rule that decides which bucket a subscriber falls in lives in this file;
report_notes.py and build_report.py only word and render the result.

How a record is read
- Month = the UTC month of beehiiv's `created` (the day the record entered beehiiv), the same clock the
  dashboard uses. The walk is cut at END so the last month is a clean "through Nov 17".
- A record whose status is "invalid" (the address failed beehiiv's validation or hard-bounced) is not a
  subscriber and is left out of every count, as beehiiv's own growth report does: with them removed the
  walk reproduces beehiiv's daily "subscribed" figure to the record (cross_check.py).
- beehiiv keeps, per subscriber, the tools they finished (`Tools Tried (Pipe-Separated)`) and the UTM
  medium of each of those visits (`UTM Media (Comma-Separated)`), both in the order they happened. The
  FIRST entry is the visit that created the subscriber; later entries are an existing reader coming back,
  which is not where the subscriber came from. Some writers left a leading separator ("|Who Attracts You",
  ",cpc": the Sep uploads and the tools from Sep 29 to Oct 8), so empty entries are skipped.
- Those two lists only describe the sign-up visit for records created AFTER the tools started writing
  them (measured hour by hour in the walk): UTM media from 2026-03-27 15:00 UTC, the tools list from
  2026-03-31 10:00 UTC. On an older record their first entry is a later visit, so:
    * nobody created before TOOLS_FROM is counted as coming from the study (the older tools field, which
      did record the sign-up tool from Mar 10, never names the study);
    * ad sign-ups created before MEDIA_FROM cannot be seen on the record and are ESTIMATED from GA4:
      "Submitted Email" events in cpc sessions on CT's own tool pages, times the share of such events
      that became a new tagged subscriber once tagging existed (calibration window CAL).
- Partner ad campaigns (MailList Accelerator: BlueDot, ACE, FarmKind, HIP, Hive) arrive with an
  `MLA Tags` value and no tool of their own. Those pages are fed by paid campaigns (98% google/cpc in GA4
  in Jan-Feb, Meta paid social later), so they count as Ads, in their own bucket.
- The upload of 2026-01-01 01:15 UTC can only hold people who signed up in December 2025 (tools did not
  write to beehiiv directly until Mar 10; sign-ups were uploaded in batches). It is set aside as backlog.
"""
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data" / "subscriptions.jsonl"
CROSS = HERE / "cross_checks.json"
OUT = HERE / "datapoints.json"
UTC = timezone.utc

END = datetime(2026, 11, 18, tzinfo=UTC)             # exclusive: the report covers Jan 1 to Nov 17
BACKLOG_UNTIL = datetime(2026, 1, 1, 2, tzinfo=UTC)  # the Jan 1 01:15 UTC upload of December sign-ups
API_FROM = datetime(2026, 3, 10, tzinfo=UTC)         # tools create subscribers directly; last batch Mar 9
MEDIA_FROM = datetime(2026, 3, 27, 15, tzinfo=UTC)   # tools write each visit's UTM medium
TOOLS_FROM = datetime(2026, 3, 31, 10, tzinfo=UTC)   # tools write the ordered tools list
CAL = (date(2026, 3, 28), date(2026, 4, 30))         # first full days with tags: calibrates the estimate
# Months whose GA4 ad-session counts are unusable for the low/high ratio: GA4 recorded nothing on the
# UPT pages from Jul 22 to Aug 10, 2026, while its ad campaign kept producing subscribers.
RATIO_SKIP_MONTHS = ("2026-07", "2026-08")

# The study's three viral waves (UTC days). For each, the Tools bucket is compared with its own baseline
# to see how many people the wave sent to OTHER tools first (they are not study sign-ups on the record).
WAVES = (("Aug 3-14", date(2026, 8, 3), date(2026, 8, 14)),
         ("Sep 7-18", date(2026, 9, 7), date(2026, 9, 18)),
         ("Oct 21-23", date(2026, 10, 21), date(2026, 10, 23)))
WAVE_BASELINE_DAYS = 14
LAUNCH = (date(2026, 3, 23), date(2026, 3, 26))  # the Unique Traits Test launch days

STUDY_TOOL = "who attracts you"
ADS_MEDIA = {"cpc", "paid_social"}
TOOLS_FIELD = "Tools Tried (Pipe-Separated)"
OLD_TOOLS_FIELD = "Tools Tried (DEPRECATED)"
MEDIA_FIELD = "UTM Media (Comma-Separated)"
MLA_FIELD = "MLA Tags (Comma-Separated)"
DATING_FIELD = "Dating App Updates"  # opt-in offered by the study and its dating-app waitlist
LEAF_FIELD = "Leaf"
BLANK = {"", "(none)", "(not set)", "none"}
INVALID = "invalid"

BACKLOG, STUDY, ADS, PARTNER_ADS = "backlog", "study", "ads", "partner_ads"
TOOLS, FORMS, PODCAST, LEAF, UPLOADS, RECOMMENDATIONS = "tools", "forms", "podcast", "leaf", "uploads", "recommendations"
EXCLUDED = (BACKLOG, STUDY, ADS, PARTNER_ADS)
INCLUDED = (TOOLS, FORMS, PODCAST, RECOMMENDATIONS, LEAF, UPLOADS)
LABELS = {
    BACKLOG: "December sign-ups uploaded Jan 1",
    STUDY: "Who Attracts You study",
    ADS: "Ads (cpc tag)",
    PARTNER_ADS: "Partner ad campaigns (MLA)",
    TOOLS: "Tools",
    FORMS: "Sign-up forms, challenges, workshops",
    PODCAST: "Podcast site",
    RECOMMENDATIONS: "beehiiv recommendations",
    LEAF: "Leaf student batches",
    UPLOADS: "Other bulk uploads",
}


# ---------- reading one record ----------

def created(row: dict) -> datetime:
    return datetime.fromtimestamp(row["created"], tz=UTC)


def tokens(value, sep: str) -> list:
    """Non-blank entries of a separated list, lower-cased and trimmed, in their original order."""
    if not isinstance(value, str):
        return []
    return [t for t in (part.strip().lower() for part in value.split(sep)) if t not in BLANK]


def tools_tried(row: dict) -> list:
    return tokens((row.get("cf") or {}).get(TOOLS_FIELD), "|")


def has_any_tool(row: dict) -> bool:
    return bool(tools_tried(row)) or bool((row.get("cf") or {}).get(OLD_TOOLS_FIELD))


def media(row: dict) -> list:
    """UTM media of the subscriber's tool visits in order; "(none)" visits are kept as "" so that the
    first entry still means the first visit."""
    value = (row.get("cf") or {}).get(MEDIA_FIELD)
    if not isinstance(value, str):
        return []
    parts = [p.strip().lower() for p in value.split(",")]
    while parts and parts[0] == "":  # leading-separator bug
        parts.pop(0)
    return ["" if p in BLANK else p for p in parts]


def native_medium(row: dict) -> str:
    m = (row.get("utm_medium") or "").strip().lower()
    return "" if m in BLANK else m


def from_ads(row: dict) -> bool:
    """The visit that created the subscriber carried an ad medium: beehiiv's own utm_medium (set at
    creation), or the first entry of the tools' media list on a record created once that list existed."""
    if native_medium(row) in ADS_MEDIA:
        return True
    m = media(row)
    return created(row) >= MEDIA_FROM and bool(m) and m[0] in ADS_MEDIA


def touched_ads(row: dict) -> bool:
    """Any visit, first or later, carried an ad medium. The wide reading, a sensitivity check only."""
    return native_medium(row) in ADS_MEDIA or bool(ADS_MEDIA & set(media(row)))


def from_study(row: dict) -> bool:
    """Created once the tools list existed, and the first tool finished was the study, or no tool at all
    plus the study's dating-app opt-in (its waitlist form and the uploads of earlier participants)."""
    if created(row) < TOOLS_FROM:
        return False
    tools = tools_tried(row)
    if tools:
        return tools[0] == STUDY_TOOL
    return bool((row.get("cf") or {}).get(DATING_FIELD))


def touched_study(row: dict) -> bool:
    """Took the study at any point or carries its opt-in. The wide reading, sensitivity only."""
    return STUDY_TOOL in tools_tried(row) or bool((row.get("cf") or {}).get(DATING_FIELD))


def from_partner_ads(row: dict) -> bool:
    """Signed up on a partner-branded (MailList Accelerator) page: an MLA tag and no tool of their own."""
    return bool((row.get("cf") or {}).get(MLA_FIELD)) and not has_any_tool(row)


def is_subscriber(row: dict) -> bool:
    return row.get("status") != INVALID


def bucket(row: dict) -> str:
    """One bucket per subscriber, tested in this order. A record that is both study and ad counts as
    study (the overlap is reported separately)."""
    channel = (row.get("utm_channel") or "").lower()
    when = created(row)
    if channel == "import" and when < BACKLOG_UNTIL:
        return BACKLOG
    if from_study(row):
        return STUDY
    if from_ads(row):
        return ADS
    if from_partner_ads(row):
        return PARTNER_ADS
    cf = row.get("cf") or {}
    if channel == "import":
        if cf.get(LEAF_FIELD):
            return LEAF
        if has_any_tool(row):
            return TOOLS
        flags = [k for k, v in cf.items() if v is True and k not in (DATING_FIELD, "ClearerThinking.org", "One Helpful Idea")]
        if flags:  # a workshop or challenge list uploaded as a file
            return FORMS
        # Until Mar 9 the tools' sign-ups reached beehiiv as plain twice-weekly uploads.
        return TOOLS if when < API_FROM else UPLOADS
    if channel == "recommendation":
        return RECOMMENDATIONS
    if has_any_tool(row):
        return TOOLS
    if (row.get("utm_source") or "").lower() == "podcast":
        return PODCAST
    return FORMS


def month_of(row: dict) -> str:
    return created(row).strftime("%Y-%m")


def day_of(row: dict) -> str:
    return created(row).strftime("%Y-%m-%d")


# ---------- ad sign-ups from before the tags existed ----------

def calibration_ratio(tagged_by_day: dict, ga4_by_day: dict, first: date, last: date) -> float:
    """Tagged ad sign-ups per GA4 cpc-session "Submitted Email" event over [first, last]."""
    days = [str(first + timedelta(days=i)) for i in range((last - first).days + 1)]
    events = sum(ga4_by_day.get(d, 0) for d in days)
    return sum(tagged_by_day.get(d, 0) for d in days) / events if events else 0.0


def estimate_untagged_ads(ga4_by_day: dict, tagged_by_day: dict, ratio: float, until: date) -> dict:
    """Per month, ad sign-ups the records cannot show: ratio x GA4 events on the days up to `until`
    (the last day without full tagging), minus the ad sign-ups already tagged on those days."""
    events, tagged = events_by_month(ga4_by_day, until), events_by_month(tagged_by_day, until)
    return {m: max(0, round(ratio * events[m] - tagged.get(m, 0))) for m in events}


def events_by_month(by_day: dict, until: date) -> dict:
    """Monthly sums of a per-day series over the days up to and including `until`."""
    out = Counter()
    for d, n in by_day.items():
        if d <= str(until):
            out[d[:7]] += n
    return dict(sorted(out.items()))


def monthly_ratios(tagged_by_day: dict, ga4_by_day: dict, after: date) -> dict:
    """Tagged ad sign-ups per GA4 cpc event for each full-tagging month after `after` (the spread of
    these gives the low/high bounds of the estimate)."""
    t, e = Counter(), Counter()
    for d, n in tagged_by_day.items():
        if d > str(after):
            t[d[:7]] += n
    for d, n in ga4_by_day.items():
        if d > str(after):
            e[d[:7]] += n
    return {m: round(t[m] / e[m], 3) for m in sorted(e) if e[m] and m not in RATIO_SKIP_MONTHS and m > str(after)[:7]}


# ---------- spill-over of the study's viral waves onto other tools ----------

def wave_excess(daily: dict, first: date, last: date, baseline_days: int = WAVE_BASELINE_DAYS) -> dict:
    """Sign-ups in [first, last] above the baseline, the baseline being the median day of the
    `baseline_days` before the window and the `baseline_days` after it (days with no record count 0)."""
    span = lambda a, n: [str(a + timedelta(days=i)) for i in range(n)]  # noqa: E731
    window = span(first, (last - first).days + 1)
    around = span(first - timedelta(days=baseline_days), baseline_days) + span(last + timedelta(days=1), baseline_days)
    counts = sorted(daily.get(d, 0) for d in around)
    mid = len(counts) // 2
    baseline = counts[mid] if len(counts) % 2 else (counts[mid - 1] + counts[mid]) / 2
    in_window = sum(daily.get(d, 0) for d in window)
    return {"days": len(window), "signups": in_window, "baseline_per_day": baseline,
            "excess": round(in_window - baseline * len(window))}


# ---------- the monthly table ----------

def summarize(rows, ga4_cpc_by_day: dict = None) -> dict:
    """Per-month counts over real subscribers. With `ga4_cpc_by_day`, ad sign-ups from before MEDIA_FROM
    are estimated and taken out of the Tools bucket; without it the estimate is zero."""
    months = defaultdict(lambda: {"records": 0, "invalid": 0, "buckets": Counter(), "active": Counter(),
                                  "both": 0, "kept_wide": 0})
    tagged_by_day, tools_by_day, tools_study_later_by_day = Counter(), Counter(), Counter()
    for row in rows:
        if created(row) >= END:
            continue
        m = months[month_of(row)]
        m["records"] += 1
        if not is_subscriber(row):
            m["invalid"] += 1
            continue
        b = bucket(row)
        m["buckets"][b] += 1
        if row.get("status") == "active":
            m["active"][b] += 1
        if b == ADS:
            tagged_by_day[day_of(row)] += 1
        if b == TOOLS:
            tools_by_day[day_of(row)] += 1
            tools_study_later_by_day[day_of(row)] += touched_study(row)
        if from_study(row) and from_ads(row):
            m["both"] += 1
        if b in INCLUDED and not (touched_study(row) or touched_ads(row)):
            m["kept_wide"] += 1

    untagged_last_day = MEDIA_FROM.date()  # Mar 27 was tagged only from 15:00 UTC
    est = low = high = {}
    calibration = None
    if ga4_cpc_by_day:
        ratio = calibration_ratio(tagged_by_day, ga4_cpc_by_day, *CAL)
        spread = monthly_ratios(tagged_by_day, ga4_cpc_by_day, CAL[1])
        lo, hi = min([ratio, *spread.values()]), max([ratio, *spread.values()])
        est = estimate_untagged_ads(ga4_cpc_by_day, tagged_by_day, ratio, untagged_last_day)
        low = estimate_untagged_ads(ga4_cpc_by_day, tagged_by_day, lo, untagged_last_day)
        high = estimate_untagged_ads(ga4_cpc_by_day, tagged_by_day, hi, untagged_last_day)
        calibration = {"window": [str(CAL[0]), str(CAL[1])], "ratio": round(ratio, 3), "low": round(lo, 3),
                       "high": round(hi, 3), "later_months": spread,
                       "ga4_events_before_tags": events_by_month(ga4_cpc_by_day, untagged_last_day)}

    out = []
    for month in sorted(months):
        m = months[month]
        b = m["buckets"]
        total = m["records"] - m["invalid"]
        on_record = sum(b[k] for k in INCLUDED)
        e = min(est.get(month, 0), b[TOOLS])
        e_low, e_high = min(low.get(month, 0), b[TOOLS]), min(high.get(month, 0), b[TOOLS])
        active_on_record = sum(m["active"][k] for k in INCLUDED)
        # The estimated ad sign-ups are assumed to have stayed subscribed at the month's Tools rate.
        active_share = m["active"][TOOLS] / b[TOOLS] if b[TOOLS] else 0
        out.append({
            "month": month,
            "records": m["records"],
            "invalid": m["invalid"],
            "total": total,
            "buckets": {k: b[k] for k in EXCLUDED + INCLUDED},
            "ads_untagged_est": e,
            "ads_all": b[ADS] + b[PARTNER_ADS] + e,
            "kept_on_record": on_record,
            "kept": on_record - e,
            "kept_low": on_record - e_high,
            "kept_high": on_record - e_low,
            "kept_tools": b[TOOLS] - e,
            "kept_active": round(active_on_record - e * active_share),
            "kept_wide": m["kept_wide"],
            "study_and_ads": m["both"],
            "estimated": e > 0,
        })
    waves = [{"name": name, "first": str(a), "last": str(b), **wave_excess(tools_by_day, a, b),
              "later_took_study": sum(n for d, n in tools_study_later_by_day.items() if str(a) <= d <= str(b))}
             for name, a, b in WAVES]
    return {"months": out, "calibration": calibration, "waves": waves}


def context(rows) -> dict:
    """Descriptive extras the report's notes quote: the Leaf batch days and the Unique Traits Test launch."""
    leaf_days, launch = Counter(), Counter()
    for row in rows:
        if not is_subscriber(row) or created(row) >= END:
            continue
        if bucket(row) == LEAF:
            leaf_days[day_of(row)] += 1
        if LAUNCH[0] <= created(row).date() <= LAUNCH[1]:
            launch["subscribers"] += 1
            launch["unique_traits_only"] += (row.get("cf") or {}).get(OLD_TOOLS_FIELD) == ["Unique Traits Test"]
    return {"leaf_batches": {d: n for d, n in sorted(leaf_days.items()) if n >= 100},
            "unique_traits_launch": {"first": str(LAUNCH[0]), "last": str(LAUNCH[1]), **launch}}


def load_rows(path: Path = DATA):
    with path.open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def main():
    rows = list(load_rows())
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate subscription ids in the walk"
    ga4 = json.loads(CROSS.read_text()).get("ga4_cpc_daily")
    assert isinstance(ga4, dict) and "error" not in ga4, "cross_checks.json has no GA4 cpc series: run fetch_cross_checks.py"
    result = summarize(rows, ga4)
    result["context"] = context(rows)
    result["records_walked"] = len(rows)
    result["through"] = str((END - timedelta(days=1)).date())
    result["partial_through_day"] = (END - timedelta(days=1)).day
    result["labels"] = LABELS
    result["cutoffs"] = {"media_from": MEDIA_FROM.isoformat(), "tools_from": TOOLS_FROM.isoformat(),
                         "api_from": API_FROM.isoformat()}
    OUT.write_text(json.dumps(result, indent=1))
    print("calibration:", result["calibration"])
    for w in result["waves"]:
        print("wave", w)
    print("context:", result["context"])
    for m in result["months"]:
        print(m["month"], "subscribers", m["total"], "| kept", m["kept"], f"({m['kept_low']}-{m['kept_high']})",
              "active", m["kept_active"], "| untagged ads est", m["ads_untagged_est"], dict(m["buckets"]))


if __name__ == "__main__":
    main()
