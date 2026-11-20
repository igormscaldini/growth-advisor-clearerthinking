"""Tests for the ct-carousel skill's slide builder (pure functions only, no rendering)."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude/skills/ct-carousel/scripts"))
import ct_carousel as c  # noqa: E402

APPROVED_SPEC = ROOT / "reports/job_change_carousel_2026-11-20_src/carousel.json"
# sha256 of CSS + OWL + the six original icons, as approved by Igor on 2026-11-20.
APPROVED_LOOK = "af15fe35ef1ad7440db07fd6c01bee843522167300ac530c6d763f259d43dc8c"
ORIGINAL_ICONS = ("compass", "puzzle", "search", "coins", "flask", "sun")


def spec(**over):
    s = {"slug": "t", "date": "2026-01-01", "title": ["Dark line", "Blue line"],
         "takeaways": [{"icon": "sun", "headline": "H one.", "paragraphs": ["P one."]},
                       {"icon": "coins", "headline": "H two.", "paragraphs": ["A.", "B."], "list": ["x", "y"]}]}
    s.update(over)
    return s


def test_look_is_unchanged():
    look = c.CSS + c.OWL + "".join(f"{k}{c.ICONS[k]}" for k in ORIGINAL_ICONS)
    assert hashlib.sha256(look.encode()).hexdigest() == APPROVED_LOOK, \
        "Carousel look changed: every carousel must match the approved one. Revert, or get Igor's OK and re-pin."


def test_approved_spec_is_valid():
    assert c.validate(json.loads(APPROVED_SPEC.read_text(encoding="utf-8"))) == []


def test_slide_count_and_order():
    out = c.slides(spec())
    assert len(out) == 4
    assert out[0][0] == "Cover: Dark line Blue line"
    assert [a for a, _ in out[1:3]] == ["H one.", "H two."]
    assert out[3][0] == "Read the full article on ClearerThinking.org/Blog"


def test_defaults_cover_label_and_end_lines():
    html = c.cover_body(spec(), 4)
    assert "2 Key Takeaways" in html
    assert "ClearerThinking.org/Blog" in c.end_body(spec(), 4)
    assert "Custom" in c.end_body(spec(end_lines=["Custom", "x.org"]), 4)


def test_end_slide_has_owl_and_no_save_note():
    html = c.end_body(spec(), 4)
    assert 'class="owl"' in html and "Save this post" not in html


def test_list_sits_after_first_paragraph():
    html = c.takeaway_body(spec(), 1, 4)
    assert html.index("<p>A.</p>") < html.index('class="list"') < html.index("<p>B.</p>")
    assert "Key takeaway 2 of 2" in html


def test_dots_mark_current_slide():
    html = c.dots(2, 4)
    assert html.count("<span") == 4
    assert html.count('class="on"') == 1
    assert html.split("<span")[3].startswith(' class="on"')


def test_validate_catches_problems():
    assert any("unknown icon" in e for e in c.validate(spec(takeaways=[{"icon": "nope", "headline": "h", "paragraphs": ["p"]}])))
    assert any("headline" in e for e in c.validate(spec(takeaways=[{"icon": "sun", "headline": "x" * 76, "paragraphs": ["p"]}])))
    assert any("body" in e for e in c.validate(spec(takeaways=[{"icon": "sun", "headline": "h", "paragraphs": ["x" * 331]}])))
    assert any("em dash" in e for e in c.validate(spec(title=["a — b", "c"])))
    assert any("allowed" in e for e in c.validate(spec(takeaways=[])))
    assert c.validate({"slug": "x"})[0].startswith("missing")
