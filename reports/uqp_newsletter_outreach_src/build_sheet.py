"""Newsletter outreach sheet for the Unanswered Questions in Psychology Prize (Oct 2026).

Input: one or more JSON arrays of newsletter contacts (the research agents' output, kept
OUT of the repo: they hold named people's work emails) plus an optional overrides JSON
keyed by slug with hand-written `hook_sentence` / `skip` / field corrections.
Output: a formatted Google Sheet (Contacts + drafts, Blurb, Method tabs) and a CSV copy
in ~/Downloads. Igor sends every email himself from his own address.

Run: .venv/bin/python reports/uqp_newsletter_outreach_src/build_sheet.py contacts1.json [contacts2.json ...]
         [--overrides overrides.json] [--csv-only]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PRIZE_URL = "https://programs.clearerthinking.org/unanswered-questions-in-psychology/"
DEADLINE = "November 10, 2026"
SIGNATURE = "Igor Scaldini\nClearer Research and Clearer Thinking\nclearerthinking.org"

COLUMNS = [
    "#", "Tier", "University", "Department", "Newsletter", "Newsletter URL",
    "Audience, frequency, how to submit", "Contact name", "Role", "Email",
    "Where the email was found", "Contact type", "Confidence", "Tracking link",
    "Subject", "Email draft", "Status", "Sent on", "Notes",
]
STATUS_OPTIONS = ["Not sent", "Sent", "Replied", "Published", "Declined", "Bounced"]

BLURB_SHORT = (
    "Unanswered Questions in Psychology Prize: call for submissions\n"
    "What question in psychology most needs an answer? Clearer Research, led by Spencer "
    "Greenberg, is collecting the field's most important open questions. Each winning "
    "question receives $400, chosen by a vote of current and former academic psychologists. "
    "Anyone may submit, and it takes about ten minutes. Deadline: " + DEADLINE + ". "
    "Submit at {link}"
)

BLURB_LONG = (
    "Unanswered Questions in Psychology Prize: call for submissions\n\n"
    "Clearer Research, the research arm of ClearerThinking.org led by Spencer Greenberg, is "
    "collecting the most important unanswered questions in psychology. Submit the question "
    "you think the field most needs to answer, with a short explanation of why it matters.\n\n"
    "Each winning question receives $400. Winners are chosen by a vote of current and former "
    "academic psychologists, and the Clearer Research team only shortlists; it does not vote.\n\n"
    "Example questions: \"What are the deep, underlying, modifiable psychological causes of why "
    "some people have higher long-term subjective well-being than others?\" and \"What scalable "
    "psychological interventions can reduce polarization and between-group animosity without "
    "suppressing legitimate disagreement?\"\n\n"
    "Anyone may submit, and it takes about ten minutes. Deadline: " + DEADLINE + ".\n"
    "Submit at {link}"
)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:40]


def tracking_link(slug: str) -> str:
    return f"{PRIZE_URL}?src=nl_{slug}"


def first_name(contact_name: str) -> str:
    """'Dr. Jane Q. Doe' -> 'Jane'; empty or non-person strings -> ''."""
    name = (contact_name or "").strip()
    if not name:
        return ""
    parts = [p for p in re.split(r"\s+", name) if p]
    honorifics = {"dr", "dr.", "prof", "prof.", "professor", "mr", "mr.", "ms", "ms.", "mrs", "mrs."}
    while parts and parts[0].lower() in honorifics:
        parts = parts[1:]
    if not parts:
        return ""
    first = parts[0].strip(",")
    if len(first) <= 1 or not first[0].isalpha():
        return ""
    return first


NON_PERSON = ("office", "department", "reception", "psychology", "general", "committee", "team")


def is_person(contact_name: str) -> bool:
    n = (contact_name or "").lower()
    return bool(n) and not any(w in n for w in NON_PERSON)


def prose_department(department: str) -> str:
    """'Department of Psychology (Faculty of Arts and Sciences) - note' -> 'the Department of Psychology'."""
    d = re.sub(r"\s*\([^)]*\)", "", department or "").split(";")[0].split(" - ")[0].strip().rstrip(",")
    if not d:
        return "the psychology department"
    if re.match(r"^(Department|College|Graduate Association|Duke Institute|Psychology Undergraduate)", d):
        d = "the " + d
    return d


def prose_university(university: str) -> str:
    u = (university or "").strip()
    return ("the " + u) if re.match(r"^(University|College) ", u) else u


def draft_email(row: dict) -> tuple[str, str]:
    """Return (subject, body) for one contact. Pure function, tested.

    `hook_sentence` (hand-written per row) opens the request paragraph; `ask_sentence`
    replaces the default ask for rows that need a specific one (weekly bulletins, annual
    newsletters that will not run before the deadline, student associations, etc.).
    """
    newsletter = (row.get("newsletter_name") or "").strip()
    department = prose_department(row.get("department", ""))
    university = row["university"]
    ctype = row.get("contact_type", "")
    link = tracking_link(row["slug"])
    hook = (row.get("hook_sentence") or "").strip()
    tail = "It is ready to paste, and I'm happy to trim it or adjust it to your format."

    name = first_name(row.get("contact_name", "")) if is_person(row.get("contact_name", "")) else ""
    greeting = f"Hi {name}," if name else "Hello,"

    if row.get("ask_sentence"):
        ask = row["ask_sentence"].strip()
    elif not newsletter:
        ask = (f"Could you forward the short item below to the department's faculty and graduate "
               f"students, or pass it to whoever sends department announcements? {tail}")
    elif ctype == "department office":
        ask = (f"Could you pass this along to whoever puts together {newsletter}, or to the person "
               f"who handles announcements for the department? If the next issue comes after the "
               f"deadline, a forward to the faculty and graduate student lists would help just as much. {tail}")
    elif ctype == "chair/DGS":
        ask = (f"I know this is not a typical request. Could you forward the short item below to "
               f"your faculty and graduate students, or pass it to whoever manages {newsletter}? {tail}")
    elif ctype == "form only":
        ask = (f"I'm submitting the short item below through your announcements form, and I "
               f"wanted to send it to you directly as well in case that is easier. {tail}")
    else:
        ask = (f"Would you be willing to include the short item below in {newsletter}, or, if the "
               f"next issue comes after the deadline, forward it to the department's faculty and "
               f"graduate student lists? {tail}")

    if newsletter:
        subject = f"A call for submissions for {newsletter}"
    else:
        subject = f"A call for submissions for psychology faculty and graduate students at {university}"

    intro_hook = (hook + " ") if hook else ""
    body = (
        f"{greeting}\n\n"
        f"I'm Igor Scaldini, and I work with Spencer Greenberg's team at Clearer Research, the "
        f"research arm of ClearerThinking.org. We're running the Unanswered Questions in "
        f"Psychology Prize, and I'd love to reach the faculty, postdocs and graduate students "
        f"of {department} at {prose_university(university)}.\n\n"
        f"The idea is simple: submit the question in psychology you think most needs an answer. "
        f"Each winning question earns $400, and the winners are chosen by a vote of current and "
        f"former academic psychologists. Submitting takes about ten minutes, and the deadline is "
        f"{DEADLINE}.\n\n"
        f"{intro_hook}{ask}\n\n"
        f"Thank you for considering it,\n{SIGNATURE}\n\n"
        f"----- Suggested item -----\n\n"
        f"{BLURB_SHORT.format(link=link)}"
    )
    return subject, body


def load_contacts(paths: list[Path], overrides: dict | None = None) -> list[dict]:
    """Merge the agents' JSON files, apply overrides, drop unusable rows, dedupe.

    Duplicate = same university and newsletter name (first file wins). A university with
    two different newsletters keeps both, the second with a longer slug. Overrides are keyed
    by the university slug (or the long slug for a second newsletter).
    """
    overrides = overrides or {}
    seen_keys: set[str] = set()
    out: list[dict] = []
    for p in paths:
        for item in json.loads(Path(p).read_text()):
            item = dict(item)
            item["university"] = re.sub(r"\s*\(extra\)\s*", "", item["university"]).strip()
            key = slugify(item["university"] + " " + (item.get("newsletter_name") or ""))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            slug = slugify(item["university"])
            if any(o["slug"] == slug for o in out):
                slug = slug + "_2"
            item["slug"] = slug
            item.update(overrides.get(slug, {}))
            if item.get("skip"):
                continue
            if not (item.get("contact_email") or item.get("contact_type") == "form only"):
                continue
            item.setdefault("tier", 3)
            out.append(item)
    order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda r: (int(r["tier"]), order.get(r.get("confidence", "low"), 2)))
    return out


def build_rows(contacts: list[dict]) -> list[dict]:
    rows = []
    for i, c in enumerate(contacts, 1):
        subject, body = draft_email(c)
        rows.append({
            "#": i,
            "Tier": c.get("tier", 3),
            "University": c["university"],
            "Department": c.get("department", ""),
            "Newsletter": c.get("newsletter_name", ""),
            "Newsletter URL": c.get("newsletter_url", ""),
            "Audience, frequency, how to submit": c.get("newsletter_notes", ""),
            "Contact name": c.get("contact_name", ""),
            "Role": c.get("contact_role", ""),
            "Email": c.get("contact_email", ""),
            "Where the email was found": c.get("email_source_url", ""),
            "Contact type": c.get("contact_type", ""),
            "Confidence": c.get("confidence", ""),
            "Tracking link": tracking_link(c["slug"]),
            "Subject": subject,
            "Email draft": body,
            "Status": "Not sent",
            "Sent on": "",
            "Notes": c.get("notes", ""),
        })
    return rows


def method_rows(stamp: str, n: int) -> list[list[str]]:
    return [
        ["How this list was built", stamp],
        ["Scope", "US university psychology departments (or the closest equivalent) with a department newsletter, "
                  "plus a few college-level or graduate-program newsletters where the department has none."],
        ["Evidence rule", "Every email appears verbatim on the page in 'Where the email was found' (fetched on the build date). "
                          "No address was guessed from a name pattern. 'form only' rows have a submission form instead of an email."],
        ["Contact priority", "1. Newsletter editor or department communications coordinator. 2. Department office email. "
                             "3. Chair or director of graduate studies. The 'Contact type' column says which one each row is."],
        ["Tier", "1 = live department newsletter that reaches faculty and graduate students, with a named editor, communications "
                 "contact or submission route. 2 = a live newsletter, but alumni- or undergraduate-facing, college- or institute-level, "
                 "annual (next issue after the deadline), or reachable only through a general inbox. 3 = no current newsletter found; "
                 "an office or communications contact who can forward the item to faculty and graduate students."],
        ["Confidence", "high = email on a .edu page and the newsletter clearly exists; medium = one of the two is weaker; low = both are weak. "
                       "Re-check low rows before sending."],
        ["Tracking link", "Each row's link carries ?src=nl_<university>. GA4 records the full page URL, so visits per newsletter can be counted "
                          "there. The form itself does not store the parameter, so submissions are matched to newsletters by date and email domain."],
        ["Sending", "Igor sends each draft by hand from his own address. Update Status and Sent on as you go. "
                    "Suggested follow-up: one reminder about a week later to rows still at 'Sent'."],
        ["Rows", str(n)],
    ]


def create_sheet(rows: list[dict], title: str, stamp: str) -> str:
    from sheets_client import get_client

    svc = get_client()
    tabs = ["Contacts + drafts", "Blurb", "Method"]
    created = svc.spreadsheets().create(body={
        "properties": {"title": title},
        "sheets": [{"properties": {"title": t}} for t in tabs],
    }).execute()
    sid = created["spreadsheetId"]
    gids = {sh["properties"]["title"]: sh["properties"]["sheetId"] for sh in created["sheets"]}

    values = [COLUMNS] + [[str(r[c]) for c in COLUMNS] for r in rows]
    blurb = [
        ["Ready-to-paste items for the newsletter editors", stamp],
        [],
        ["Short item (used inside every draft)", BLURB_SHORT.format(link=PRIZE_URL)],
        [],
        ["Long item (if an editor wants more)", BLURB_LONG.format(link=PRIZE_URL)],
        [],
        ["Plain link", PRIZE_URL],
        ["Deadline", DEADLINE],
        ["Prize", "$400 per winning question; winners chosen by a vote of current and former academic psychologists"],
    ]
    svc.spreadsheets().values().batchUpdate(spreadsheetId=sid, body={
        "valueInputOption": "RAW",
        "data": [
            {"range": f"'{tabs[0]}'!A1", "values": values},
            {"range": f"'{tabs[1]}'!A1", "values": blurb},
            {"range": f"'{tabs[2]}'!A1", "values": method_rows(stamp, len(rows))},
        ],
    }).execute()

    g0 = gids[tabs[0]]
    widths = {"#": 40, "Tier": 50, "University": 200, "Department": 200, "Newsletter": 200, "Newsletter URL": 220,
              "Audience, frequency, how to submit": 320, "Contact name": 160, "Role": 200, "Email": 230,
              "Where the email was found": 220, "Contact type": 130, "Confidence": 90, "Tracking link": 220,
              "Subject": 260, "Email draft": 520, "Status": 110, "Sent on": 100, "Notes": 260}
    requests = [
        {"repeatCell": {"range": {"sheetId": g0, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True},
                                                       "backgroundColor": {"red": 0.91, "green": 0.94, "blue": 0.99}}},
                        "fields": "userEnteredFormat(textFormat.bold,backgroundColor)"}},
        {"updateSheetProperties": {"properties": {"sheetId": g0, "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 2}},
                                   "fields": "gridProperties(frozenRowCount,frozenColumnCount)"}},
        {"repeatCell": {"range": {"sheetId": g0, "startRowIndex": 1, "endRowIndex": len(rows) + 1},
                        "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                        "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}},
        {"setDataValidation": {
            "range": {"sheetId": g0, "startRowIndex": 1, "endRowIndex": len(rows) + 1,
                      "startColumnIndex": COLUMNS.index("Status"), "endColumnIndex": COLUMNS.index("Status") + 1},
            "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in STATUS_OPTIONS]},
                     "showCustomUi": True, "strict": False}}},
    ]
    for i, col in enumerate(COLUMNS):
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": g0, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": widths[col]}, "fields": "pixelSize"}})
    for t in tabs[1:]:
        g = gids[t]
        requests += [
            {"updateDimensionProperties": {"range": {"sheetId": g, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                                           "properties": {"pixelSize": 260}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": g, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
                                           "properties": {"pixelSize": 700}, "fields": "pixelSize"}},
            {"repeatCell": {"range": {"sheetId": g}, "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                            "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}},
            {"repeatCell": {"range": {"sheetId": g, "startColumnIndex": 0, "endColumnIndex": 1},
                            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}}, "fields": "userEnteredFormat.textFormat.bold"}},
        ]
    svc.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": requests}).execute()
    return f"https://docs.google.com/spreadsheets/d/{sid}"


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("contacts", nargs="+")
    ap.add_argument("--overrides")
    ap.add_argument("--csv-only", action="store_true")
    ap.add_argument("--title", default=f"UQP Prize - newsletter outreach {date.today().isoformat()}")
    args = ap.parse_args()
    overrides = json.loads(Path(args.overrides).read_text()) if args.overrides else {}
    contacts = load_contacts([Path(p) for p in args.contacts], overrides)
    rows = build_rows(contacts)
    stamp = date.today().isoformat()
    out = Path.home() / "Downloads" / f"uqp_newsletter_outreach_{stamp}.csv"
    write_csv(rows, out)
    print(f"{len(rows)} rows -> {out}")
    if not args.csv_only:
        print(create_sheet(rows, args.title, stamp))


if __name__ == "__main__":
    main()
