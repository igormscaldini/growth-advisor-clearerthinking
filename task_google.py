"""Google Docs, Sheets and Slides for the task bot: create new files in Igor's Drive.

Igor's choices (2026-11-22): the bot may only touch files it creates itself (Google's
`drive.file` permission: it cannot see or open anything else in his Drive) and it never shares
them (he clicks Share himself). Every file goes into one "Claude tasks" folder.

The login is a token of its own (secrets/taskbot-google-token.json locally, the
TASKBOT_GOOGLE_TOKEN_JSON secret on GitHub), minted once by `python auth_taskbot_google.py`, so
the shared token every other report uses keeps its scopes.

The builders (markdown_to_html, clean_tabs, slide_requests, notes_requests) are pure and
unit-tested; the functions that call Google are thin.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_FILE = ROOT / "secrets" / "taskbot-google-token.json"
FOLDER_NAME = "Claude tasks"
FOLDER_MIME = "application/vnd.google-apps.folder"
DOC_MIME = "application/vnd.google-apps.document"

MAX_DOC_CHARS = 100_000
MAX_TABS, MAX_ROWS, MAX_COLS, MAX_CELL_CHARS = 10, 5_000, 50, 5_000
MAX_SLIDES, MAX_SLIDE_CHARS = 40, 3_000
# Formulas are allowed (totals, budgets), except those that fetch from or call out to the web
# when the sheet is opened: a forwarded email could otherwise plant one that leaks the sheet.
BLOCKED_FORMULA_RE = re.compile(r"\b(IMPORT\w*|IMAGE|HYPERLINK)\s*\(", re.I)
LAYOUTS = {"title": "TITLE", "section": "SECTION_HEADER", "content": "TITLE_AND_BODY"}


class BadInput(ValueError):
    """The content the model passed cannot be turned into a file as is (too big, wrong shape)."""


# --- pure builders ---------------------------------------------------------------------------
def markdown_to_html(title: str, content: str) -> str:
    """A whole HTML page from Markdown. Google converts it to a Doc on upload, keeping headings,
    bold, lists, links and tables."""
    import markdown

    if len(content) > MAX_DOC_CHARS:
        raise BadInput(f"the document is longer than {MAX_DOC_CHARS:,} characters")
    body = markdown.markdown(content, extensions=["tables", "sane_lists"])
    from html import escape

    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{escape(title)}</title></head>"
            f"<body>{body}</body></html>")


def _cell(value) -> str | int | float | bool:
    if value is None:
        return ""
    if isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    if len(text) > MAX_CELL_CHARS:
        raise BadInput(f"a cell is longer than {MAX_CELL_CHARS:,} characters")
    if text.lstrip().startswith("=") and BLOCKED_FORMULA_RE.search(text):
        raise BadInput("formulas that fetch from the web (IMPORT..., IMAGE, HYPERLINK) are not allowed")
    return text


def clean_tabs(tabs) -> list[dict]:
    """[{"name": str, "rows": [[cell, ...], ...]}] checked and normalised. Tab names are unique
    and within Google's rules; ragged rows are fine."""
    if not isinstance(tabs, list) or not tabs:
        raise BadInput("tabs must be a non-empty list of {name, rows}")
    if len(tabs) > MAX_TABS:
        raise BadInput(f"at most {MAX_TABS} tabs")
    out, seen = [], set()
    for i, tab in enumerate(tabs, 1):
        tab = tab or {}
        name = re.sub(r"[\[\]:*?/\\']", " ", str(tab.get("name") or f"Sheet{i}")).strip()[:90] or f"Sheet{i}"
        while name.lower() in seen:
            name = f"{name} ({i})"
        seen.add(name.lower())
        rows = tab.get("rows") or []
        if not isinstance(rows, list) or any(not isinstance(r, list) for r in rows):
            raise BadInput(f"tab {name!r}: rows must be a list of lists")
        if len(rows) > MAX_ROWS or any(len(r) > MAX_COLS for r in rows):
            raise BadInput(f"tab {name!r}: at most {MAX_ROWS:,} rows and {MAX_COLS} columns")
        out.append({"name": name, "rows": [[_cell(c) for c in r] for r in rows]})
    return out


def _lines(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def clean_slides(slides) -> list[dict]:
    """[{"layout": title|section|content, "title": str, "body": str or [lines], "notes": str}]."""
    if not isinstance(slides, list) or not slides:
        raise BadInput("slides must be a non-empty list")
    if len(slides) > MAX_SLIDES:
        raise BadInput(f"at most {MAX_SLIDES} slides")
    out = []
    for s in slides:
        s = s or {}
        layout = str(s.get("layout") or "content").lower()
        if layout not in LAYOUTS:
            raise BadInput(f"layout must be one of {', '.join(LAYOUTS)}")
        slide = {"layout": layout, "title": str(s.get("title") or "").strip(),
                 "body": _lines(s.get("body")), "notes": str(s.get("notes") or "").strip()}
        if sum(len(x) for x in (slide["title"], slide["notes"], *slide["body"])) > MAX_SLIDE_CHARS:
            raise BadInput(f"a slide holds at most {MAX_SLIDE_CHARS:,} characters")
        out.append(slide)
    return out


def slide_id(i: int) -> str:
    """Google wants object ids of 5+ characters."""
    return f"slide_{i}"


def slide_requests(slides: list[dict], remove_id: str | None = None) -> list[dict]:
    """Slides API batchUpdate requests: one slide per entry from Google's standard layouts, text
    in the layout's own boxes, content bodies as bullets. `remove_id` = the blank slide a new
    presentation starts with."""
    reqs = []
    for i, s in enumerate(slides):
        sid = slide_id(i)
        tid, bid = f"{sid}_title", f"{sid}_body"
        title_type = "CENTERED_TITLE" if s["layout"] == "title" else "TITLE"
        body_type = "SUBTITLE" if s["layout"] in ("title", "section") else "BODY"
        mappings = [{"layoutPlaceholder": {"type": title_type, "index": 0}, "objectId": tid}]
        if s["body"]:
            mappings.append({"layoutPlaceholder": {"type": body_type, "index": 0}, "objectId": bid})
        reqs.append({"createSlide": {"objectId": sid, "insertionIndex": i,
                                     "slideLayoutReference": {"predefinedLayout": LAYOUTS[s["layout"]]},
                                     "placeholderIdMappings": mappings}})
        if s["title"]:
            reqs.append({"insertText": {"objectId": tid, "text": s["title"]}})
        if s["body"]:
            reqs.append({"insertText": {"objectId": bid, "text": "\n".join(s["body"])}})
            if s["layout"] == "content":
                reqs.append({"createParagraphBullets": {"objectId": bid, "textRange": {"type": "ALL"},
                                                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
    if remove_id:
        reqs.append({"deleteObject": {"objectId": remove_id}})
    return reqs


def notes_requests(presentation: dict, slides: list[dict]) -> list[dict]:
    """Speaker notes go in each slide's notes box, whose id exists only once the slide does."""
    by_id = {p["objectId"]: p for p in presentation.get("slides", [])}
    reqs = []
    for i, s in enumerate(slides):
        page = by_id.get(slide_id(i))
        notes_id = (((page or {}).get("slideProperties") or {}).get("notesPage") or {}) \
            .get("notesProperties", {}).get("speakerNotesObjectId")
        if s["notes"] and notes_id:
            reqs.append({"insertText": {"objectId": notes_id, "text": s["notes"]}})
    return reqs


# --- Google -----------------------------------------------------------------------------------
def credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not TOKEN_FILE.exists():
        raise RuntimeError("the bot has no Google Drive login yet (run python auth_taskbot_google.py once)")
    creds = Credentials.from_authorized_user_info(json.loads(TOKEN_FILE.read_text()), SCOPES)
    if not creds.valid:
        creds.refresh(Request())
    return creds


def _service(name: str, version: str):
    from googleapiclient.discovery import build

    return build(name, version, credentials=credentials(), cache_discovery=False)


def folder_id(drive) -> str:
    """The "Claude tasks" folder, created on first use. With drive.file the search only sees
    folders this login created, so a folder of the same name made by Igor is never reused."""
    q = f"name = '{FOLDER_NAME}' and mimeType = '{FOLDER_MIME}' and trashed = false"
    found = drive.files().list(q=q, fields="files(id)", pageSize=1).execute().get("files", [])
    if found:
        return found[0]["id"]
    return drive.files().create(body={"name": FOLDER_NAME, "mimeType": FOLDER_MIME},
                                fields="id").execute()["id"]


def _move_into_folder(drive, file_id: str) -> None:
    parent = folder_id(drive)
    current = drive.files().get(fileId=file_id, fields="parents").execute().get("parents", [])
    drive.files().update(fileId=file_id, addParents=parent, removeParents=",".join(current),
                         fields="id").execute()


def create_doc(title: str, content: str) -> dict:
    from googleapiclient.http import MediaInMemoryUpload

    html = markdown_to_html(title, content)
    drive = _service("drive", "v3")
    f = drive.files().create(
        body={"name": title, "mimeType": DOC_MIME, "parents": [folder_id(drive)]},
        media_body=MediaInMemoryUpload(html.encode("utf-8"), mimetype="text/html"),
        fields="id,webViewLink").execute()
    return {"id": f["id"], "url": f["webViewLink"]}


def create_sheet(title: str, tabs: list[dict]) -> dict:
    sheets = _service("sheets", "v4")
    book = sheets.spreadsheets().create(body={
        "properties": {"title": title},
        "sheets": [{"properties": {"title": t["name"], "gridProperties": {"frozenRowCount": 1}}} for t in tabs],
    }, fields="spreadsheetId,spreadsheetUrl,sheets.properties").execute()
    data = [{"range": f"'{t['name']}'!A1", "values": t["rows"]} for t in tabs if t["rows"]]
    if data:
        sheets.spreadsheets().values().batchUpdate(spreadsheetId=book["spreadsheetId"], body={
            "valueInputOption": "USER_ENTERED", "data": data}).execute()
    fmt = []
    for sh in book["sheets"]:
        gid = sh["properties"]["sheetId"]
        fmt.append({"repeatCell": {"range": {"sheetId": gid, "startRowIndex": 0, "endRowIndex": 1},
                                   "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                                   "fields": "userEnteredFormat.textFormat.bold"}})
        fmt.append({"autoResizeDimensions": {"dimensions": {"sheetId": gid, "dimension": "COLUMNS"}}})
    sheets.spreadsheets().batchUpdate(spreadsheetId=book["spreadsheetId"], body={"requests": fmt}).execute()
    _move_into_folder(_service("drive", "v3"), book["spreadsheetId"])
    return {"id": book["spreadsheetId"], "url": book["spreadsheetUrl"]}


def create_slides(title: str, slides: list[dict]) -> dict:
    api = _service("slides", "v1")
    deck = api.presentations().create(body={"title": title}).execute()
    pid = deck["presentationId"]
    blank = (deck.get("slides") or [{}])[0].get("objectId")
    api.presentations().batchUpdate(presentationId=pid, body={"requests": slide_requests(slides, blank)}).execute()
    notes = notes_requests(api.presentations().get(presentationId=pid).execute(), slides)
    if notes:
        api.presentations().batchUpdate(presentationId=pid, body={"requests": notes}).execute()
    _move_into_folder(_service("drive", "v3"), pid)
    return {"id": pid, "url": f"https://docs.google.com/presentation/d/{pid}/edit"}
