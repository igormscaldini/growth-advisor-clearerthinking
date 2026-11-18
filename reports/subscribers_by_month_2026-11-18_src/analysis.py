"""New beehiiv subscribers per month in 2026, with Ads (cpc) and the Who Attracts You study taken out.

    .venv/bin/python reports/subscribers_by_month_2026-11-18_src/analysis.py

Reads data/subscriptions.jsonl (from fetch_data.py), writes datapoints.json. Every rule that decides which
bucket a subscriber falls in lives in this file; build_report.py only renders.

How a record is read
- beehiiv keeps, per subscriber, the tools they finished (`Tools Tried (Pipe-Separated)`) and the UTM
  medium of each of those visits (`UTM Media (Comma-Separated)`), both in the order they happened. The
  FIRST entry is therefore the visit that created the subscriber: later entries are an existing reader
  coming back, which is not where the subscriber came from. Between 2026-09-29 and 2026-10-08 the tools
  wrote these lists with a leading separator ("|Who Attracts You", ",cpc"), so empty entries are skipped.
- Month = the UTC month of beehiiv's `created` (the day the record entered beehiiv), the same clock the
  dashboard uses.
- A record whose status is "invalid" (the address failed beehiiv's validation or hard-bounced) is not a
  subscriber and is left out of every count, as beehiiv's own growth report does: with them removed the
  walk reproduces beehiiv's daily "subscribed" figure to the record (cross_check.py).
"""
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data" / "subscriptions.jsonl"
OUT = HERE / "datapoints.json"

STUDY_TOOL = "who attracts you"
ADS_MEDIUM = "cpc"
TOOLS_FIELD = "Tools Tried (Pipe-Separated)"
MEDIA_FIELD = "UTM Media (Comma-Separated)"
DATING_FIELD = "Dating App Updates"  # opt-in offered by the study and its dating-app waitlist
BLANK = {"", "(none)", "(not set)", "none"}
INVALID = "invalid"

# Buckets, in the order they are tested. The first two are the ones Igor asked to leave out.
STUDY, ADS = "study", "ads"
TOOLS, FORMS, PODCAST, LEAF, UPLOADS, RECOMMENDATIONS, OTHER = (
    "tools", "forms", "podcast", "leaf", "uploads", "recommendations", "other")
EXCLUDED = (STUDY, ADS)
INCLUDED = (TOOLS, FORMS, PODCAST, LEAF, UPLOADS, RECOMMENDATIONS, OTHER)
LABELS = {
    STUDY: "Who Attracts You study",
    ADS: "Ads (cpc)",
    TOOLS: "Tools (no ad click)",
    FORMS: "Website sign-up forms",
    PODCAST: "Podcast site",
    LEAF: "Leaf student batches",
    UPLOADS: "Other bulk uploads",
    RECOMMENDATIONS: "beehiiv recommendations",
    OTHER: "Other",
}


def tokens(value, sep: str) -> list:
    """Non-blank entries of a separated list, lower-cased and trimmed, in their original order."""
    if not isinstance(value, str):
        return []
    return [t for t in (part.strip().lower() for part in value.split(sep)) if t not in BLANK]


def tools_tried(row: dict) -> list:
    return tokens((row.get("cf") or {}).get(TOOLS_FIELD), "|")


def media(row: dict) -> list:
    """UTM media of the subscriber's tool visits in order; "(none)" visits are kept as "" so that the
    first entry still means the first visit."""
    value = (row.get("cf") or {}).get(MEDIA_FIELD)
    if not isinstance(value, str):
        return []
    parts = [p.strip().lower() for p in value.split(",")]
    while parts and parts[0] == "":  # the Sep 29-Oct 8 leading-separator bug
        parts.pop(0)
    return ["" if p in BLANK else p for p in parts]


def native_medium(row: dict) -> str:
    m = (row.get("utm_medium") or "").strip().lower()
    return "" if m in BLANK else m


def from_ads(row: dict) -> bool:
    """The visit that created the subscriber carried utm_medium=cpc (beehiiv's own field or the first
    entry of the tools' list)."""
    m = media(row)
    return native_medium(row) == ADS_MEDIUM or (bool(m) and m[0] == ADS_MEDIUM)


def touched_ads(row: dict) -> bool:
    """Any visit, first or later, carried cpc. The wide reading, used only as a sensitivity check."""
    return native_medium(row) == ADS_MEDIUM or ADS_MEDIUM in media(row)


def from_study(row: dict) -> bool:
    """The first tool the subscriber finished was the study, or they have no tool at all and carry the
    study's dating-app opt-in (its waitlist form and the uploads of earlier participants)."""
    tools = tools_tried(row)
    if tools:
        return tools[0] == STUDY_TOOL
    return bool((row.get("cf") or {}).get(DATING_FIELD))


def touched_study(row: dict) -> bool:
    """Took the study at any point or carries its opt-in. The wide reading, sensitivity only."""
    return STUDY_TOOL in tools_tried(row) or bool((row.get("cf") or {}).get(DATING_FIELD))


def bucket(row: dict) -> str:
    """One bucket per subscriber. The study is tested before ads, so a record that is both counts as
    study (the overlap is reported separately)."""
    if from_study(row):
        return STUDY
    if from_ads(row):
        return ADS
    cf = row.get("cf") or {}
    channel = (row.get("utm_channel") or "").lower()
    if channel == "import":
        return LEAF if cf.get("Leaf") else UPLOADS
    if channel == "recommendation":
        return RECOMMENDATIONS
    if tools_tried(row):
        return TOOLS
    if (row.get("utm_source") or "").lower() == "podcast":
        return PODCAST
    if channel in ("embed", "website", "api"):
        return FORMS
    return OTHER


def month_of(row: dict) -> str:
    return datetime.fromtimestamp(row["created"], tz=timezone.utc).strftime("%Y-%m")


def day_of(row: dict) -> str:
    return datetime.fromtimestamp(row["created"], tz=timezone.utc).strftime("%Y-%m-%d")


def is_subscriber(row: dict) -> bool:
    return row.get("status") != INVALID


def summarize(rows) -> dict:
    """Per-month counts over real subscribers (invalid addresses set aside): every bucket, the kept total,
    how many are still active, the study/ads overlap and the wide-reading sensitivity."""
    months = defaultdict(lambda: {"records": 0, "invalid": 0, "buckets": Counter(), "active": Counter(),
                                  "both": 0, "included_wide": 0, "imports": 0})
    for row in rows:
        m = months[month_of(row)]
        m["records"] += 1
        if not is_subscriber(row):
            m["invalid"] += 1
            continue
        b = bucket(row)
        m["buckets"][b] += 1
        if row.get("status") == "active":
            m["active"][b] += 1
        if from_study(row) and from_ads(row):
            m["both"] += 1
        if not (touched_study(row) or touched_ads(row)):
            m["included_wide"] += 1
        if (row.get("utm_channel") or "").lower() == "import":
            m["imports"] += 1
    out = []
    for month in sorted(months):
        m = months[month]
        total = m["records"] - m["invalid"]
        included = sum(m["buckets"][b] for b in INCLUDED)
        out.append({
            "month": month,
            "records": m["records"],
            "invalid": m["invalid"],
            "total": total,
            "buckets": {b: m["buckets"][b] for b in EXCLUDED + INCLUDED},
            "excluded": total - included,
            "included": included,
            "included_active": sum(m["active"][b] for b in INCLUDED),
            "included_wide": m["included_wide"],
            "study_and_ads": m["both"],
            "imports": m["imports"],
        })
    return {"months": out}


def load_rows(path: Path = DATA):
    with path.open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def main():
    rows = list(load_rows())
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate subscription ids in the walk"
    result = summarize(rows)
    subscribers = [r for r in rows if is_subscriber(r)]
    result["daily_total"] = dict(sorted(Counter(day_of(r) for r in subscribers).items()))
    result["records"] = len(rows)
    result["labels"] = LABELS
    OUT.write_text(json.dumps(result, indent=1))
    for m in result["months"]:
        print(m["month"], m["records"], "-invalid", m["invalid"], "=", m["total"], "included", m["included"], "active", m["included_active"], dict(m["buckets"]))


if __name__ == "__main__":
    main()
