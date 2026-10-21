import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reports" / "uqp_newsletter_outreach_src"))

from build_sheet import (COLUMNS, build_rows, draft_email, first_name, load_contacts,  # noqa: E402
                         slugify, tracking_link)


def base(**kw):
    row = {"university": "University of Michigan", "department": "Department of Psychology",
           "newsletter_name": "Psychology News", "contact_name": "Dr. Jane Q. Doe",
           "contact_role": "Communications Coordinator", "contact_email": "jdoe@umich.edu",
           "contact_type": "editor/comms", "slug": "university_of_michigan"}
    row.update(kw)
    return row


def test_first_name_strips_honorifics_and_handles_empty():
    assert first_name("Dr. Jane Q. Doe") == "Jane"
    assert first_name("Professor John Smith") == "John"
    assert first_name("") == ""
    assert first_name("Psychology Department") == "Psychology"  # caller decides by contact_type


def test_slug_and_tracking_link():
    assert slugify("University of Michigan") == "university_of_michigan"
    assert tracking_link("ucla") == \
        "https://programs.clearerthinking.org/unanswered-questions-in-psychology/?src=nl_ucla"


def test_editor_draft_is_personal_and_complete():
    subject, body = draft_email(base(hook_sentence="Your Announcements section looks like the right spot."))
    assert subject == "A call for submissions for Psychology News"
    assert body.startswith("Hi Jane,")
    assert "Your Announcements section looks like the right spot. Would you be willing" in body
    assert "forward it to the department's faculty and graduate student lists" in body
    assert "Department of Psychology at University of Michigan" in body
    assert "$400" in body and "November 10, 2026" in body
    assert "?src=nl_university_of_michigan" in body
    assert "—" not in body and "—" not in subject  # no em dashes, Igor's rule


def test_department_office_draft_uses_generic_greeting_and_forwarding_ask():
    subject, body = draft_email(base(contact_name="Psychology Department", contact_type="department office",
                                     contact_email="psych@umich.edu"))
    assert body.startswith("Hello,")
    assert "pass this along to whoever puts together Psychology News" in body


def test_named_office_contact_is_greeted_by_first_name():
    _, body = draft_email(base(contact_name="Krista Lester", contact_type="department office"))
    assert body.startswith("Hi Krista,")


def test_no_newsletter_row_gets_forwarding_ask_and_university_subject():
    subject, body = draft_email(base(newsletter_name="", contact_type="department office"))
    assert subject == "A call for submissions for psychology faculty and graduate students at University of Michigan"
    assert "forward the short item below to the department's faculty and graduate students" in body


def test_ask_sentence_override_replaces_default_ask():
    _, body = draft_email(base(ask_sentence="Could you drop it in Psych Weekly?", hook_sentence="Hook."))
    assert "Hook. Could you drop it in Psych Weekly?\n\nThank you" in body
    assert "Would you be willing" not in body


def test_chair_draft_changes_subject_and_ask():
    subject, body = draft_email(base(contact_type="chair/DGS", contact_name="Prof. Ann Lee"))
    assert subject.startswith("A $400 prize for unanswered questions in psychology")
    assert body.startswith("Hi Ann,")
    assert "forward the short item below to your faculty and graduate students" in body


def test_load_contacts_merges_dedupes_applies_overrides_and_drops_unusable(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps([
        {"university": "Yale University", "newsletter_name": "Psych News", "contact_email": "x@yale.edu",
         "contact_type": "editor/comms"},
        {"university": "Brown University", "newsletter_name": "", "contact_email": "", "contact_type": "none found"},
        {"university": "Duke University", "newsletter_name": "Form NL", "contact_email": "", "contact_type": "form only"},
    ]))
    b.write_text(json.dumps([
        {"university": "Yale University", "newsletter_name": "Psych News", "contact_email": "dup@yale.edu",
         "contact_type": "editor/comms"},
        {"university": "Rice University", "newsletter_name": "Rice NL", "contact_email": "r@rice.edu",
         "contact_type": "editor/comms"},
    ]))
    overrides = {"rice_university": {"skip": True}, "yale_university": {"hook_sentence": "Hook."}}
    out = load_contacts([a, b], overrides)
    slugs = [c["slug"] for c in out]
    assert slugs == ["yale_university", "duke_university"]   # Brown dropped (no route), Rice skipped, Yale deduped
    assert all(c["tier"] == 3 for c in out)
    assert out[0]["contact_email"] == "x@yale.edu"            # first occurrence wins
    assert out[0]["hook_sentence"] == "Hook."


def test_second_newsletter_of_same_university_gets_suffixed_slug_and_sorting_by_tier(tmp_path):
    a = tmp_path / "a.json"
    a.write_text(json.dumps([
        {"university": "University of Minnesota (extra)", "newsletter_name": "Brain Wave", "contact_email": "a@umn.edu",
         "contact_type": "department office", "confidence": "medium"},
        {"university": "University of Minnesota", "newsletter_name": "Psych Scoop", "contact_email": "b@umn.edu",
         "contact_type": "editor/comms", "confidence": "medium"},
    ]))
    out = load_contacts([a], {"university_of_minnesota": {"tier": 2}, "university_of_minnesota_2": {"tier": 1}})
    assert [c["slug"] for c in out] == ["university_of_minnesota_2", "university_of_minnesota"]
    assert out[1]["university"] == "University of Minnesota"  # "(extra)" stripped


def test_build_rows_has_every_column_and_numbering():
    rows = build_rows([base(), base(university="Yale University", slug="yale_university")])
    assert [r["#"] for r in rows] == [1, 2]
    assert all(list(r.keys()) == COLUMNS for r in rows)
    assert rows[1]["Tracking link"].endswith("?src=nl_yale_university")
    assert rows[0]["Status"] == "Not sent"
