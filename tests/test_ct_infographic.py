"""Tests for the ct-infographic skill's kit and its worked example (pure functions, hand-worked answers)."""
from datetime import datetime
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude/skills/ct-infographic/scripts"))
import ct_infographic as kit  # noqa: E402

SRC = ROOT / "reports/integrative_complexity_staircase_2026-11-06_src/build.py"
spec = importlib.util.spec_from_file_location("staircase_build", SRC)
staircase = importlib.util.module_from_spec(spec)
spec.loader.exec_module(staircase)


# ---- timestamp -----------------------------------------------------------------------------
@pytest.mark.parametrize("moment, expected", [
    (datetime(2026, 11, 6, 8, 5), "2026-11-06 8:05am"),
    (datetime(2026, 11, 6, 15, 30), "2026-11-06 3:30pm"),
    (datetime(2026, 1, 2, 0, 0), "2026-01-02 12:00am"),     # midnight
    (datetime(2026, 1, 2, 12, 0), "2026-01-02 12:00pm"),    # noon
    (datetime(2026, 12, 31, 10, 9), "2026-12-31 10:09am"),  # two-digit hour keeps both digits
])
def test_timestamp_format(moment, expected):
    assert kit.timestamp(moment) == expected


# ---- contrast (WCAG) -----------------------------------------------------------------------
def test_contrast_extremes_are_exact():
    assert kit.contrast("#ffffff", "#000000") == pytest.approx(21.0)   # (1 + .05) / (0 + .05)
    assert kit.contrast("#3b83f1", "#3b83f1") == pytest.approx(1.0)


def test_contrast_is_symmetric():
    assert kit.contrast("#303030", "#dcebfc") == pytest.approx(kit.contrast("#dcebfc", "#303030"))


def test_contrast_mid_grey_worked_by_hand():
    # #808080: channel 128/255 = 0.50196 -> ((0.50196 + 0.055) / 1.055) ** 2.4 = 0.21586 luminance.
    # Against white: 1.05 / 0.26586 = 3.949.
    assert kit.contrast("#808080", "#ffffff") == pytest.approx(3.949, abs=0.005)


def test_palette_text_rules_hold():
    """The rules the skill states: dark text on the first three blues, white only on the last."""
    for fill in kit.BLUE_RAMP[:3] + kit.BLUE_TINTS:
        assert kit.contrast(kit.INK, fill) >= 4.5
    assert kit.contrast("#ffffff", kit.BLUE_RAMP[4]) >= 4.5
    assert kit.contrast("#ffffff", kit.BLUE_RAMP[3]) < 4.5      # why white text needs the darkest step


# ---- display size --------------------------------------------------------------------------
def test_display_px_scales_linearly():
    assert kit.display_px(32, 1600, 800) == pytest.approx(16.0)     # half the width, half the size
    assert kit.display_px(27, 1600, 1600) == pytest.approx(27.0)
    assert kit.display_px(27, 1600, 375) == pytest.approx(6.328, abs=0.001)   # 27 * 375 / 1600


# ---- logo and page shell -------------------------------------------------------------------
def test_logo_markup_is_inline_svg_without_xml_header():
    svg = kit.logo_markup()
    assert svg.startswith('<svg class="logo" ')
    assert "<?xml" not in svg and svg.rstrip().endswith("</svg>")


def test_page_html_two_line_title_and_auto_height():
    html = kit.page_html(body_html='<div id="mid">BODY</div>', title_line_1="Dark line", title_line_2="Blue line",
                         width=1600, stamp="2026-11-06 8:05am", png_path="/x/out.png", alt="An alt")
    assert '<div class="l1">Dark line</div><div class="l2">Blue line</div>' in html
    assert "#canvas { width:1600px; background:#fff;  }" in html      # no fixed height
    assert html.index('<div class="title">') < html.index("BODY") < html.index('<div class="footer">')
    assert "built 2026-11-06 8:05am" in html and "/x/out.png" in html and 'aria-label="An alt"' in html
    assert "<defs>" not in html.split("<body>")[1].split('<div id="canvas"')[0]   # no shared defs asked for


def test_page_html_fixed_height_single_line_and_defs():
    html = kit.page_html(body_html="B", title_line_2="Only blue", width=1600, height=1600,
                         svg_defs='<marker id="m"></marker>', css=".x { color:red; }")
    assert "height:1600px; display:flex; flex-direction:column;" in html
    assert '<div class="l1">' not in html and '<div class="l2">Only blue</div>' in html
    assert '<defs><marker id="m"></marker></defs>' in html
    assert ".x { color:red; }" in html


def test_page_html_without_title_has_no_title_block():
    assert '<div class="title">' not in kit.page_html(body_html="B")


def test_formats_export_at_multiples_of_1080_for_social():
    for name in ("square", "portrait"):
        f = kit.FORMATS[name]
        assert f["width"] * f["scale"] == pytest.approx(2160)
    assert kit.FORMATS["square"]["height"] * kit.FORMATS["square"]["scale"] == pytest.approx(2160)
    assert kit.FORMATS["portrait"]["height"] * kit.FORMATS["portrait"]["scale"] == pytest.approx(2700)
    assert kit.FORMATS["landscape"]["height"] is None


# ---- worked example: the staircase ---------------------------------------------------------
@pytest.mark.parametrize("fmt", ["landscape", "square"])
def test_staircase_contains_every_level_and_group(fmt):
    html = staircase.build_html(staircase.LAYOUTS[fmt], stamp="2026-11-06 8:05am")
    for number, (heading, text) in enumerate(staircase.LEVELS, start=1):
        assert f"Level {number}</div>" in html and heading in html and text in html
    for _, _, heading, text in staircase.GROUPS:
        assert heading in html and text in html
    assert html.count('class="col"') == 7 and html.count('class="group"') == 2


def test_staircase_steps_rise_by_a_constant_amount():
    lay = staircase.LAYOUTS["square"]
    heights = [int(staircase.step(n, "h", "t", lay).split("height:")[1].split("px")[0]) for n in range(1, 8)]
    assert heights[0] == lay["base_h"]
    assert {b - a for a, b in zip(heights, heights[1:])} == {lay["step_h"]}


def test_staircase_glyphs_follow_the_story():
    one, hint, two, linked, ring = (staircase.glyph(n) for n in (1, 2, 3, 5, 7))
    assert one.count("<circle") == 1                                   # one angle
    assert hint.count("<circle") == 2 and "stroke-dasharray" in hint   # second angle only hinted
    assert two.count("<circle") == 2 and "stroke-dasharray" not in two and "<path" not in two
    assert linked.count("<path") == 2 and "marker-end" in linked       # two arrows
    assert ring.count("<circle") == 4                                  # ring + two angles + centre dot
