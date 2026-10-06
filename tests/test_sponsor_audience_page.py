"""Tests for the pure helpers in reports/ct_sponsor_audience_report_2026-10-06_src/build_page.py.

build_page loads its JSON inputs at import, so the module is imported from source with the loaders
pointed at tiny synthetic files.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reports" / "ct_sponsor_audience_report_2026-10-06_src" / "build_page.py"


@pytest.fixture(scope="module")
def bp(tmp_path_factory):
    """Import build_page with GA4 and survey inputs replaced by minimal synthetic data."""
    tmp = tmp_path_factory.mktemp("page")
    src_dir = tmp / "reports" / "ct_sponsor_audience_report_2026-10-06_src"
    personas = tmp / "reports" / "ct_audience_personas_2026-09-25_src"
    src_dir.mkdir(parents=True)
    personas.mkdir(parents=True)
    (src_dir / "ga4_datapoints.json").write_text(json.dumps({"window": {"start": "2025-10-01", "end": "2026-09-30"},
                                                              "demographics": {"age": [], "gender": []}, "newsletter": {}}))
    (personas / "datapoints.json").write_text(json.dumps({"survey_2026_03": {}, "paths": {}, "career_2026_09": {}}))
    code = SRC.read_text().replace("HERE = Path(__file__).resolve().parent", f"HERE = Path({str(src_dir)!r})")
    mod_path = src_dir / "build_page.py"
    mod_path.write_text(code)
    spec = importlib.util.spec_from_file_location("sponsor_page", mod_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sponsor_page"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_shares_percentages(bp):
    out = bp.shares([("A", 50), ("B", 25)], 200)
    assert out == [{"label": "A", "count": 50, "pct": 25.0}, {"label": "B", "count": 25, "pct": 12.5}]


def test_demographic_shares_sums_months_filters_host_and_drops_unknown_and_excluded_month(bp):
    rows = [
        {"month": "202510", "host": "www", "value": "18-24", "users": 30},
        {"month": "202511", "host": "www", "value": "18-24", "users": 10},
        {"month": "202511", "host": "www", "value": "65+", "users": 10},
        {"month": "202511", "host": "www", "value": "unknown", "users": 1000},
        {"month": "202608", "host": "www", "value": "18-24", "users": 500},   # excluded month
        {"month": "202511", "host": "tools", "value": "18-24", "users": 999},  # other host
    ]
    out = bp.demographic_shares(rows, "www", exclude_months=("202608",), order=["18-24", "25-34", "65+"])
    assert out["n"] == 50
    assert [(r["label"], r["count"]) for r in out["rows"]] == [("18-24", 40), ("25-34", 0), ("65+", 10)]
    assert [r["pct"] for r in out["rows"]] == pytest.approx([80.0, 0.0, 20.0])


def test_demographic_shares_default_order_is_by_size(bp):
    rows = [{"month": "202510", "host": "h", "value": "small", "users": 1}, {"month": "202510", "host": "h", "value": "big", "users": 9}]
    assert [r["label"] for r in bp.demographic_shares(rows, "h", exclude_months=())["rows"]] == ["big", "small"]


def test_engaged_shares_uses_engaged_sessions_and_drops_not_set(bp):
    rows = [
        {"value": "United States", "sessions": 900, "engaged_sessions": 300},
        {"value": "Ashburn-like scanner land", "sessions": 500, "engaged_sessions": 0},
        {"value": "(not set)", "sessions": 100, "engaged_sessions": 50},
        {"value": "United Kingdom", "sessions": 200, "engaged_sessions": 100},
    ]
    out = bp.engaged_shares(rows, top=2)
    assert out["n"] == 400
    assert [(r["label"], r["pct"]) for r in out["rows"]] == [("United States", 75.0), ("Ashburn-like scanner land", 0.0)]


@pytest.mark.parametrize("country,bucket", [
    ("United States", "United States"), ("Canada", "Canada"), ("United Kingdom", "United Kingdom"),
    ("Germany", "Europe"), ("Ireland", "Europe"), ("Russia", "Europe"), ("India", "Asia"), ("Singapore", "Asia"),
    ("Türkiye", "Asia"), ("Australia", "Other"), ("Brazil", "Other"), ("South Africa", "Other"),
])
def test_region(bp, country, bucket):
    assert bp.region(country) == bucket


def test_language_bucket(bp):
    assert [bp.language_bucket(l) for l in ("English", "German", "Spanish", "French", "Dutch")] == \
        ["English", "German", "Spanish", "Others", "Others"]


def test_bucket_shares_sums_engaged_sessions_in_order_and_drops_not_set(bp):
    rows = [
        {"value": "Germany", "sessions": 50, "engaged_sessions": 20},
        {"value": "United States", "sessions": 500, "engaged_sessions": 100},
        {"value": "France", "sessions": 50, "engaged_sessions": 30},
        {"value": "India", "sessions": 80, "engaged_sessions": 40},
        {"value": "Australia", "sessions": 10, "engaged_sessions": 10},
        {"value": "(not set)", "sessions": 900, "engaged_sessions": 300},
    ]
    out = bp.bucket_shares(rows, bp.region, bp.REGION_ORDER)
    assert out["n"] == 200
    assert [(r["label"], r["count"]) for r in out["rows"]] == [("United States", 100), ("Europe", 50), ("Asia", 40), ("Other", 10)]
    assert [r["pct"] for r in out["rows"]] == pytest.approx([50.0, 25.0, 20.0, 5.0])


def test_chart_collects_spec(bp):
    bp.CHARTS.clear()
    html = bp.chart(bp.spec("c1", "Title", 100, bp.shares([("x", 10), ("EA", 20)], 100), question="Q?", wide=True))
    assert 'id="c1"' in html and "(n = 100)" in html and "Q?" in html
    spec = bp.CHARTS[-1]
    assert spec["data"] == [10.0, 20.0] and spec["counts"] == [10, 20]
    assert spec["wrap"] == 48 and spec["labels"] == ["x", "EA"]
