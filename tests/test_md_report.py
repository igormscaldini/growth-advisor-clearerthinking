"""Tests for reports/md_report.py (shared Markdown -> HTML page for report builders)."""
import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

REPORTS = Path(__file__).resolve().parents[1] / "reports"
spec = importlib.util.spec_from_file_location("md_report", REPORTS / "md_report.py")
mr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mr)


def test_timestamp_afternoon_is_zero_padded_12_hour_with_lowercase_suffix():
    assert mr.timestamp(datetime(2026, 11, 6, 15, 5)) == "2026-11-06 03:05pm"


def test_timestamp_midnight_and_noon_edges():
    assert mr.timestamp(datetime(2026, 1, 2, 0, 7)) == "2026-01-02 12:07am"
    assert mr.timestamp(datetime(2026, 1, 2, 12, 0)) == "2026-01-02 12:00pm"


def test_render_page_exact_output_for_a_tiny_document():
    html = mr.render_page("# Hi\n\nBody.", "T")
    assert html == ("<!doctype html><html><head><meta charset='utf-8'>"
                    "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                    f"<title>T</title><style>{mr.BASE_CSS}</style></head>"
                    '<body><h1 id="hi">Hi</h1>\n<p>Body.</p></body></html>')


def test_subtitle_goes_directly_under_the_first_h1_only():
    html = mr.render_page("# One\n\nText.\n\n# Two", "T", subtitle="2026-11-06 03:05pm")
    assert '<h1 id="one">One</h1>\n<p>2026-11-06 03:05pm</p>\n<p>Text.</p>' in html
    assert html.count("2026-11-06 03:05pm") == 1


def test_subtitle_without_a_heading_is_an_error_not_a_silent_drop():
    with pytest.raises(ValueError):
        mr.render_page("No heading here.", "T", subtitle="x")


def test_extra_css_is_appended_and_extensions_are_respected():
    md = "| a | b |\n|---|---|\n| 1 | 2 |"
    assert "<table>" not in mr.render_page(md, "T")
    html = mr.render_page(md, "T", extra_css="table{x:y}", extensions=("tables",))
    assert "<table>" in html and "table{x:y}</style>" in html


def test_year_end_report_still_renders_byte_identically():
    """The first user of the shared shell: its committed HTML must not change when the helper does."""
    src = REPORTS / "year_end_appeal_theories_of_change_2026-10-19_src" / "theories_of_change.md"
    out = REPORTS / "year_end_appeal_theories_of_change_2026-10-19.html"
    html = mr.render_page(src.read_text(), "Year-end appeal: theories of change",
                          "h2#sources + ol{font-size:14px;color:#444}\n")
    assert html == out.read_text()
