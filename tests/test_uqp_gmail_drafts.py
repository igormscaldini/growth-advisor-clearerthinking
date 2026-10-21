import base64
import sys
from email import message_from_bytes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reports" / "uqp_newsletter_outreach_src"))

from create_gmail_drafts import build_draft_message, rows_to_draft  # noqa: E402


def test_build_draft_message_round_trips_headers_and_utf8_body():
    body = "Hi Evan,\n\nEach winning question earns $400 and the deadline is November 10, 2026.\nNuñez"
    res = build_draft_message("eyeadon@umass.edu", "A call for submissions for PBS Newsletter", body)
    msg = message_from_bytes(base64.urlsafe_b64decode(res["raw"]))
    assert msg["To"] == "eyeadon@umass.edu"
    assert msg["Subject"] == "A call for submissions for PBS Newsletter"
    assert msg.get_payload(decode=True).decode("utf-8") == body
    assert msg.get_content_type() == "text/plain"


def test_rows_to_draft_skips_existing_and_blank_emails():
    rows = [
        {"Email": "a@x.edu", "Subject": "S1", "Email draft": "b"},
        {"Email": "B@x.edu", "Subject": "S2", "Email draft": "b"},   # already drafted (case-insensitive)
        {"Email": "", "Subject": "S3", "Email draft": "b"},          # no address
    ]
    todo, skipped = rows_to_draft(rows, {("b@x.edu", "S2")})
    assert [r["Subject"] for r in todo] == ["S1"]
    assert [r["Subject"] for r in skipped] == ["S2", "S3"]
