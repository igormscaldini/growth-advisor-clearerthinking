"""Accountability partner introductions for the Overcoming Procrastination workshop (Nov 24, 2026).

Two scheduled steps for one round (default "Dec 1"), run by .github/workflows/accountability-pairs.yml:

  match  (evening of Nov 30, US Eastern): reads the hand-reviewed "Dec 1" tab of the pairing sheet, keeps every pair
         whose two people are still opted in, pairs anyone new or left without a partner (Claude reads their projects,
         as in the hand matching; a plain word-overlap matcher if that fails), and writes the tab "Dec 1 (to send)".
         Igor gets an email with the sheet link. Unticking "Send" on a row holds that pair.
  send   (Dec 1 from 14:00 UTC = 9am ET): one email per pair, To the two (or three) people only, From
         igor@clearerthinking.org (a verified Gmail send-as alias). "Sent at" is written right after each email, so a
         re-run never sends a pair twice. Igor gets a summary.

Who is in: the LATEST GuidedTrack row per email (program 39185) has accountabilityOptIn = 1 and a gender answer
(`partnerGenderAnswer`, the raw answer: the derived `partnerGender` is blank for 12 real opt-ins), minus every email on
the sheet's "Not paired" tab, test addresses, and addresses beehiiv marks invalid. Women with women, men with men.

The intro text is the Google Doc INTRO_DOC (first line "Subject: ..."), fetched at send time so Igor's last edits are
used; bots/accountability_intro_email.txt is the fallback copy.

This repo's Actions logs are PUBLIC: print counts only, never an address or a project.

    python accountability_pairs.py match [--force]          # writes the to-send tab (replaces it with --force)
    python accountability_pairs.py send                     # waits for SEND_AT unless --now
    python accountability_pairs.py test --to you@example.com  # preview tab + ONE sample email to that address
"""
from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).parent
GT_PROGRAM_ID = 39185
SHEET_ENV = "ACCOUNTABILITY_SHEET_ID"
INTRO_DOC = "1vXSeEnBRequ8nATxQIGQe0Lf7tfyU3PQQBDeTGpjipE"
FALLBACK_TEMPLATE = ROOT / "bots" / "accountability_intro_email.txt"
FROM_HEADER = "Igor Scaldini <igor@clearerthinking.org>"
IGOR = "igormscaldini@gmail.com"
SEND_AT = {"Dec 1": datetime(2026, 12, 1, 14, 0, tzinfo=timezone.utc)}
TEST_MARKERS = ("igormscaldini", "+qa", "+healthcheck")
MAX_EMAILS = 150  # far above one round (~91); a bug that multiplies rows stops here instead of mailing people
SEND_HEADERS = ["Pair", "Group", "Person A", "Person B", "Person C", "Project A", "Project B", "Project C",
                "Match", "Why", "Check", "Send", "Sent at"]
GROUPS = {"Woman": "Women", "Man": "Men"}


# --- who is in (pure) -----------------------------------------------------------------------------------------------

def norm(email: str) -> str:
    return (email or "").strip().lower()


def is_test(email: str) -> bool:
    return any(m in norm(email) for m in TEST_MARKERS)


def eligible_people(rows: list[dict], excluded: set[str]) -> dict[str, dict]:
    """email -> {email, gender, project} for everyone whose latest finished sign-up asks for a partner.
    A row counts as a sign-up when accountabilityOptIn is "0" or "1"; the newest one per email decides, so a later
    "no" removes an earlier "yes". The project is the newest non-empty one that person wrote."""
    by_email: dict[str, list[dict]] = {}
    for r in rows:
        if (r.get("accountabilityOptIn") or "") in ("0", "1") and norm(r.get("signupEmail")):
            by_email.setdefault(norm(r["signupEmail"]), []).append(r)
    out = {}
    for e, rs in by_email.items():
        rs.sort(key=lambda r: r.get("Time Started (UTC)") or "")
        last = rs[-1]
        gender = (last.get("partnerGenderAnswer") or "").strip()
        if last["accountabilityOptIn"] != "1" or gender not in GROUPS or e in excluded or is_test(e):
            continue
        project = next((re.sub(r"\s+", " ", r.get("projectToWorkOn") or "").strip()
                        for r in reversed(rs) if (r.get("projectToWorkOn") or "").strip()), "")
        out[e] = {"email": (last.get("signupEmail") or "").strip(), "gender": gender, "project": project}
    return out


def keep_pairs(reviewed: list[dict], people: dict[str, dict]) -> tuple[list[dict], list[str]]:
    """Reviewed pairs ({"emails": [...], ...}) whose members are all still eligible and of one gender. Returns the kept
    pairs and the emails of eligible people not in any kept pair (new sign-ups and partners of people who left)."""
    kept, used = [], set()
    for p in reviewed:
        es = [norm(e) for e in p["emails"] if norm(e)]
        if len(es) >= 2 and all(e in people and e not in used for e in es) \
                and len({people[e]["gender"] for e in es}) == 1:
            kept.append({**p, "emails": es})
            used.update(es)
    return kept, [e for e in people if e not in used]


def tokens(text: str) -> set[str]:
    stop = {"the", "and", "for", "my", "to", "a", "of", "on", "in", "i", "it", "is", "with", "that", "this", "an",
            "or", "at", "be", "do", "get", "more", "some", "keep", "putting", "off", "working", "work", "finally"}
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2 and w not in stop}


def overlap(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def fallback_pairs(emails: list[str], people: dict[str, dict], kept: list[dict]) -> list[dict]:
    """Deterministic matcher for when Claude is unavailable: per gender, people who named a project are paired greedily
    by word overlap, the others with each other; one person left over joins the kept pair of their gender whose
    projects overlap theirs most (a group of three)."""
    new: list[dict] = []
    for g in GROUPS:
        pool = sorted(e for e in emails if people[e]["gender"] == g)
        with_p = [e for e in pool if people[e]["project"]]
        without = [e for e in pool if not people[e]["project"]]
        while len(with_p) > 1:
            a = with_p.pop(0)
            b = max(with_p, key=lambda x: overlap(people[a]["project"], people[x]["project"]))
            with_p.remove(b)
            new.append({"emails": [a, b], "match": "Loose", "why": "Matched by shared words in the projects"})
        rest = with_p + without
        while len(rest) > 1:
            new.append({"emails": [rest.pop(0), rest.pop(0)], "match": "No project",
                        "why": "Paired without a project to match on"})
        if rest:
            attach_single(rest[0], people, kept + new)
    return new


def attach_single(email: str, people: dict, pairs: list[dict]) -> None:
    """Add one person to the two-person pair of the same gender with the closest projects (makes a group of three)."""
    g = people[email]["gender"]
    cands = [p for p in pairs if len(p["emails"]) == 2 and people[p["emails"][0]]["gender"] == g]
    if not cands:
        raise RuntimeError(f"no pair to join for a leftover person in group {GROUPS[g]}")
    best = max(cands, key=lambda p: max(overlap(people[email]["project"], people[e]["project"]) for e in p["emails"]))
    best["emails"].append(email)
    best["why"] = (best.get("why") or "") + " (group of three: odd number of people)"


def validate_plan(pairs: list[dict], people: dict[str, dict], previous: set[frozenset] = frozenset()) -> None:
    """Raise unless every eligible person is in exactly one group of two or three people of one gender, nobody
    ineligible is in, and no two people meet again."""
    seen: list[str] = []
    for p in pairs:
        es = p["emails"]
        if not 2 <= len(es) <= 3:
            raise ValueError(f"group of {len(es)}")
        if any(e not in people for e in es):
            raise ValueError("someone in the plan is not an eligible opt-in")
        if len({people[e]["gender"] for e in es}) != 1:
            raise ValueError("a group mixes genders")
        for i, a in enumerate(es):
            for b in es[i + 1:]:
                if frozenset((a, b)) in previous:
                    raise ValueError("two people would meet again")
        seen += es
    if len(seen) != len(set(seen)):
        raise ValueError("someone is in two groups")
    if set(seen) != set(people):
        raise ValueError(f"{len(set(people) - set(seen))} eligible people left out")


# --- matching with Claude --------------------------------------------------------------------------------------------

CLAUDE_SYSTEM = """You match accountability partners for a workshop on overcoming procrastination. Each person wrote
the project they keep putting off (or nothing). Pair people whose projects are most alike, so they can relate to each
other's work: same kind of project first (a thesis with a thesis, a book with a book, a job search with a job search),
then the same broad area (academic, writing, career, creative, home, finances, admin, work tasks). People with no
project go with each other. Only pair people within the list you are given. Also flag anyone whose project suggests
they may be under 18 (for example applying to university or college, high-school exams).
Answer with JSON only."""


def claude_pairs(emails: list[str], people: dict[str, dict], kept: list[dict]) -> list[dict]:
    """Pair the leftovers with Claude, one gender at a time. People are sent as numbers with their project only (no
    address). A single leftover joins a kept pair that Claude picks. Raises if the reply is unusable."""
    import advisor_memory as mem

    new: list[dict] = []
    for g, label in GROUPS.items():
        pool = [e for e in emails if people[e]["gender"] == g]
        if not pool:
            continue
        ids = {str(i + 1): e for i, e in enumerate(pool)}
        listing = "\n".join(f'{i}: {people[e]["project"] or "(no project)"}' for i, e in ids.items())
        pairs_of_g = [p for p in kept if len(p["emails"]) == 2 and people[p["emails"][0]]["gender"] == g]
        existing = "\n".join(f'P{k + 1}: {people[p["emails"][0]]["project"] or "(no project)"} / '
                             f'{people[p["emails"][1]]["project"] or "(no project)"}' for k, p in enumerate(pairs_of_g))
        user = (f"People to pair ({label}):\n{listing}\n\n"
                + (f"There is an odd number, so exactly one person joins one of these existing pairs:\n{existing}\n\n"
                   if len(pool) % 2 else "")
                + 'Reply as {"pairs": [{"a": "1", "b": "2", "match": "Strong|Medium|Loose|No project", '
                  '"why": "few words on what they share"}], "join": {"person": "5", "pair": "P3"} or null, '
                  '"possible_minors": ["3"]}')
        text = mem.claude_text(CLAUDE_SYSTEM, user)
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        minors = {ids[i] for i in data.get("possible_minors") or [] if i in ids}
        placed = []
        for q in data.get("pairs") or []:
            a, b = ids[str(q["a"])], ids[str(q["b"])]
            why = re.sub(r"\s*[\u2014\u2013]\s*", ": ", q.get("why") or "")  # Igor's rule: no em dashes
            new.append({"emails": [a, b], "match": q.get("match") or "Medium", "why": why,
                        "minor": bool(minors & {a, b})})
            placed += [a, b]
        if len(pool) % 2:
            j = data.get("join") or {}
            single = ids[str(j["person"])]
            target = pairs_of_g[int(str(j["pair"]).lstrip("P")) - 1]
            target["emails"].append(single)
            target["why"] = (target.get("why") or "") + " (group of three: odd number of people)"
            target["minor"] = target.get("minor") or single in minors
            placed.append(single)
        if sorted(placed) != sorted(pool):
            raise ValueError("Claude's pairing does not cover every leftover exactly once")
    return new


# --- the intro email (pure) ------------------------------------------------------------------------------------------

def parse_template(text: str) -> tuple[str, str]:
    """(subject, body) from the Doc's plain-text export: first non-empty line 'Subject: ...', then the body. Bullets
    become '•', runs of blank lines collapse to one."""
    lines = text.replace("﻿", "").replace("\r\n", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines or not lines[0].lower().startswith("subject:"):
        raise ValueError("the intro template must start with 'Subject: ...'")
    subject = lines[0].split(":", 1)[1].strip()
    body = "\n".join(re.sub(r"^\s*\*\s+", "• ", ln).rstrip() for ln in lines[1:])
    body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"
    if len(body) < 200:
        raise ValueError("the intro template body looks empty")
    return subject, body


def body_for(body: str, n: int) -> str:
    """The template speaks to two people; adjust it for a group of three."""
    if n == 2:
        return body
    return (body.replace("introduces the two of you", "introduces the three of you")
                .replace("You're both on it", "You're all on it")
                .replace("you both can decide", "you can all decide")
                .replace("someone new", "new people"))


def build_message(subject: str, body: str, to: list[str], round_name: str) -> MIMEText:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = FROM_HEADER
    msg["To"] = ", ".join(to)
    msg["X-CT-Accountability"] = round_name
    return msg


def send_due(round_name: str, now: datetime) -> bool:
    return now >= SEND_AT[round_name]


# --- I/O -------------------------------------------------------------------------------------------------------------

def _creds():
    import secrets_loader
    from google.oauth2.credentials import Credentials
    secrets_loader.materialize_ci_secrets()
    return Credentials.from_authorized_user_file(str(ROOT / "secrets" / "ga4-token.json"))


def sheets():
    from googleapiclient.discovery import build
    return build("sheets", "v4", credentials=_creds(), cache_discovery=False).spreadsheets()


def gmail():
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=_creds(), cache_discovery=False)


def sheet_id() -> str:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    sid = os.getenv(SHEET_ENV, "").strip()
    if not sid:
        raise SystemExit(f"{SHEET_ENV} is not set")
    return sid


def read_tab(svc, sid: str, tab: str) -> list[list[str]]:
    return svc.values().get(spreadsheetId=sid, range=f"'{tab}'!A1:Z500").execute().get("values", [])


def tab_exists(svc, sid: str, tab: str) -> bool:
    meta = svc.get(spreadsheetId=sid, fields="sheets.properties.title").execute()
    return any(s["properties"]["title"] == tab for s in meta["sheets"])


def records(values: list[list[str]]) -> list[dict]:
    if not values:
        return []
    head = values[0]
    return [{h: (r[i] if i < len(r) else "") for i, h in enumerate(head)} for r in values[1:]]


def gt_rows() -> list[dict]:
    import requests
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    r = requests.get(f"https://www.guidedtrack.com/programs/{GT_PROGRAM_ID}/exports?export_format=csv",
                     auth=(os.environ["GUIDED_TRACK_USERNAME"], os.environ["GUIDED_TRACK_PASSWORD"]), timeout=600)
    r.raise_for_status()
    csv.field_size_limit(10 ** 9)
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig", "replace").replace("\0", ""))))


def invalid_in_beehiiv(emails: list[str]) -> set[str]:
    """Addresses beehiiv has marked invalid (hard bounces); an intro to them would leave the partner alone."""
    import urllib.parse
    import requests
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    key, pub = os.getenv("BEEHIIV_API_KEY"), os.getenv("BEEHIIV_PUB_CLEARER_THINKING")
    if not key or not pub:
        print("[warn] no beehiiv credentials: invalid-address check skipped")
        return set()
    bad = set()
    for e in emails:
        r = requests.get(f"https://api.beehiiv.com/v2/publications/{pub}/subscriptions/by_email/"
                         f"{urllib.parse.quote(e, safe='')}", headers={"Authorization": f"Bearer {key}"}, timeout=60)
        if r.status_code == 200 and (r.json().get("data") or {}).get("status") == "invalid":
            bad.add(e)
        time.sleep(0.15)
    return bad


def intro_template() -> tuple[tuple[str, str], str]:
    import requests
    try:
        r = requests.get(f"https://docs.google.com/document/d/{INTRO_DOC}/export?format=txt", timeout=60)
        r.raise_for_status()
        return parse_template(r.content.decode("utf-8-sig")), "the Google Doc"
    except Exception as e:  # noqa: BLE001
        print(f"[warn] could not read the intro Doc ({type(e).__name__}); using the repo copy")
        return parse_template(FALLBACK_TEMPLATE.read_text()), "the repo copy (the Doc could not be read)"


def notify(subject: str, body: str) -> None:
    import email_transport
    email_transport.send_email(subject, body, IGOR, from_label="Accountability bot",
                               header_tag="accountability", to_inbox=True)


# --- the two steps ---------------------------------------------------------------------------------------------------

def match(round_name: str, tab: str, force: bool = False) -> dict:
    svc, sid = sheets(), sheet_id()
    if tab_exists(svc, sid, tab) and not force:
        print(f"'{tab}' already exists: matching skipped (pass --force to rebuild it)")
        return {"skipped": True}
    excluded = {norm(r[0]) for r in read_tab(svc, sid, "Not paired")[1:] if r and "@" in r[0]}
    people = eligible_people(gt_rows(), excluded)
    bad = invalid_in_beehiiv(sorted(people))
    for e in bad:
        people.pop(e)
    reviewed = []
    for r in records(read_tab(svc, sid, round_name)):
        reviewed.append({"emails": [r.get("Person A", ""), r.get("Person B", ""), r.get("Person C", "")],
                         "match": r.get("Match", ""), "why": r.get("Why", ""), "check": r.get("Check", ""),
                         "minor": "under 18" in (r.get("Check") or "")})
    kept, leftovers = keep_pairs(reviewed, people)
    method = "none needed"
    new: list[dict] = []
    if leftovers:
        try:
            new = claude_pairs(leftovers, people, kept)
            method = "Claude"
            validate_plan(kept + new, people)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] Claude matching failed ({type(e).__name__}); using the word-overlap matcher")
            kept, _ = keep_pairs(reviewed, people)  # undo any group of three Claude made
            new = fallback_pairs(leftovers, people, kept)
            method = "word overlap (Claude failed)"
    plan = kept + new
    validate_plan(plan, people)
    plan.sort(key=lambda p: (people[p["emails"][0]]["gender"] != "Woman", p in kept))
    rows = [SEND_HEADERS]
    for i, p in enumerate(plan, 1):
        es = p["emails"] + [""] * (3 - len(p["emails"]))
        check = p.get("check") or ""
        if p.get("minor") and "under 18" not in check:
            check = (check + "; " if check else "") + "may be under 18 (check before sending)"
        if p not in kept:
            check = (check + "; " if check else "") + "new pair, matched on Nov 30"
        rows.append([i, GROUPS[people[p["emails"][0]]["gender"]], *[people[e]["email"] if e else "" for e in es],
                     *[people[e]["project"] if e else "" for e in es], p.get("match") or "", p.get("why") or "",
                     check, not p.get("minor"), ""])
    write_tab(svc, sid, tab, rows)
    held = sum(1 for r in rows[1:] if r[11] is False)
    return {"pairs": len(plan), "people": len(people), "kept": len(kept), "new": len(new), "method": method,
            "invalid": len(bad), "held": held, "trios": sum(1 for p in plan if len(p["emails"]) == 3)}


def write_tab(svc, sid: str, tab: str, rows: list[list]) -> None:
    if tab_exists(svc, sid, tab):
        svc.values().clear(spreadsheetId=sid, range=f"'{tab}'").execute()
    else:
        svc.batchUpdate(spreadsheetId=sid, body={"requests": [{"addSheet": {"properties": {
            "title": tab, "gridProperties": {"frozenRowCount": 1}}}}]}).execute()
    svc.values().update(spreadsheetId=sid, range=f"'{tab}'!A1", valueInputOption="RAW",
                        body={"values": rows}).execute()
    gid = next(s["properties"]["sheetId"] for s in svc.get(spreadsheetId=sid).execute()["sheets"]
               if s["properties"]["title"] == tab)
    n = len(rows)
    widths = [45, 60, 230, 230, 160, 260, 260, 200, 85, 230, 260, 55, 150]
    reqs = [{"setDataValidation": {"range": {"sheetId": gid, "startRowIndex": 1, "endRowIndex": n,
                                             "startColumnIndex": 11, "endColumnIndex": 12},
                                   "rule": {"condition": {"type": "BOOLEAN"}}}},
            {"repeatCell": {"range": {"sheetId": gid, "startRowIndex": 0, "endRowIndex": 1},
                            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                            "fields": "userEnteredFormat.textFormat"}},
            {"repeatCell": {"range": {"sheetId": gid, "startRowIndex": 1, "endRowIndex": n},
                            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                            "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}}]
    reqs += [{"updateDimensionProperties": {"range": {"sheetId": gid, "dimension": "COLUMNS", "startIndex": i,
                                                      "endIndex": i + 1},
                                            "properties": {"pixelSize": w}, "fields": "pixelSize"}}
             for i, w in enumerate(widths)]
    svc.batchUpdate(spreadsheetId=sid, body={"requests": reqs}).execute()


def plan_rows(values: list[list[str]]) -> list[tuple[int, dict]]:
    """(sheet row number, record) for every pair row, after safety checks on the whole tab."""
    recs = records(values)
    if not recs or list(recs[0])[:len(SEND_HEADERS)] != SEND_HEADERS:
        raise ValueError("the to-send tab does not have the expected columns")
    out, seen = [], []
    for i, r in enumerate(recs, start=2):
        es = [norm(r[k]) for k in ("Person A", "Person B", "Person C") if norm(r[k])]
        if not es:
            continue
        if len(es) < 2 or any("@" not in e for e in es):
            raise ValueError(f"row {i} does not hold two addresses")
        seen += es
        out.append((i, {**r, "emails": es}))
    if len(seen) != len(set(seen)):
        raise ValueError("an address appears in two rows of the to-send tab")
    if sum(len(r["emails"]) for _, r in out) > MAX_EMAILS * 3:
        raise ValueError("too many rows")
    return out


def is_ticked(value) -> bool:
    return str(value).strip().upper() == "TRUE"


def send(round_name: str, tab: str, now_ok: bool) -> dict:
    if not now_ok and not send_due(round_name, datetime.now(timezone.utc)):
        print("not time to send yet")
        return {"skipped": True}
    svc, sid = sheets(), sheet_id()
    if not tab_exists(svc, sid, tab):
        print(f"'{tab}' is missing: matching first")
        match(round_name, tab)
    rows = plan_rows(read_tab(svc, sid, tab))
    todo = [(n, r) for n, r in rows if is_ticked(r.get("Send")) and not (r.get("Sent at") or "").strip()]
    if len(todo) > MAX_EMAILS:
        raise SystemExit(f"{len(todo)} emails to send is above the {MAX_EMAILS} safety cap")
    (subject, body), source = intro_template()
    g = gmail()
    sent, failed = 0, []
    for n, r in todo:
        msg = build_message(subject, body_for(body, len(r["emails"])), r["emails"], round_name)
        try:
            g.users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}
                                      ).execute()
        except Exception as e:  # noqa: BLE001
            failed.append(n)
            print(f"[error] row {n}: {type(e).__name__}")
            continue
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        svc.values().update(spreadsheetId=sid, range=f"'{tab}'!M{n}", valueInputOption="RAW",
                            body={"values": [[stamp]]}).execute()
        sent += 1
        time.sleep(1.5)
    held = sum(1 for _, r in rows if not is_ticked(r.get("Send")))
    already = sum(1 for _, r in rows if (r.get("Sent at") or "").strip())
    return {"sent": sent, "failed": len(failed), "failed_rows": failed, "held": held, "already": already,
            "source": source, "pairs": len(rows)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["match", "send", "test"])
    ap.add_argument("--round", default="Dec 1", choices=list(SEND_AT))
    ap.add_argument("--force", action="store_true", help="match: rebuild the to-send tab even if it exists")
    ap.add_argument("--now", action="store_true", help="send: do not wait for the scheduled time")
    ap.add_argument("--to", help="test: the one address that gets the sample email")
    a = ap.parse_args()
    link = f"https://docs.google.com/spreadsheets/d/{sheet_id()}/edit"
    tab = f"{a.round} (to send)"
    if a.step == "test":
        if not a.to or not is_test(a.to):
            raise SystemExit("test needs --to with one of your own test addresses")
        res = match(a.round, f"{a.round} (preview)", force=True)
        print("preview:", json.dumps(res))
        (subject, body), source = intro_template()
        msg = build_message("[TEST] " + subject, body, [a.to], a.round)
        gmail().users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}
                                        ).execute()
        print(f"sample email sent to the test address (template from {source})")
        return 0
    if a.step == "match":
        res = match(a.round, tab, force=a.force)
        print("match:", json.dumps(res))
        if not res.get("skipped"):
            notify(f"Accountability pairs for {a.round} are ready ({res['pairs']} pairs)",
                   f"{res['people']} people opted in: {res['kept']} reviewed pairs kept, {res['new']} new pairs "
                   f"(matched by {res['method']}), {res['trios']} group(s) of three, {res['invalid']} invalid "
                   f"address(es) left out.\n\n{res['held']} pair(s) are on hold (Send unticked) because someone may "
                   f"be under 18: tick Send to include them.\n\nThe intros go out automatically on {a.round} from "
                   f"9am ET. To hold a pair, untick Send on its row in the tab '{tab}':\n{link}\n")
        return 0
    res = send(a.round, tab, a.now)
    print("send:", json.dumps({k: v for k, v in res.items() if k != "failed_rows"}))
    if not res.get("skipped") and (res["sent"] or res["failed"]):
        notify(f"Accountability intros for {a.round}: {res['sent']} sent"
               + (f", {res['failed']} FAILED" if res["failed"] else ""),
               f"Sent {res['sent']} intro emails from igor@clearerthinking.org (text from {res['source']}).\n"
               f"Failed: {res['failed']} (rows {res['failed_rows']}); a later run retries them.\n"
               f"Held (Send unticked): {res['held']}. Sent in an earlier run: {res['already']}.\n\n{link}\n")
    return 1 if res.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
