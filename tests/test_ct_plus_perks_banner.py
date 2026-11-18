"""Tests for reports/ct_plus_perks_banner_2026-11-18_src/build.py (the CT+ perks banner re-flow)."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

SRC = Path(__file__).resolve().parents[1] / "reports" / "ct_plus_perks_banner_2026-11-18_src" / "build.py"
spec = importlib.util.spec_from_file_location("perks_banner", SRC)
pb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pb)

WIDTH = 1091


def flat_row(bodies=(10, 20, 30), rows=4):
    """A synthetic 3-tile row with no shadows: grey background, white cards, each card's content area filled
    with its own value, so the right answer of any re-flow can be written down by hand."""
    band = np.full((rows, WIDTH, 1), pb.BG)
    for x, value in zip(pb.X, bodies):
        band[:, x:x + pb.W] = 255
        band[:, x + pb.STRIP:x + pb.W - pb.STRIP] = value
    return band


def expected_row(columns, bodies, rows=4):
    band = np.full((rows, WIDTH, 1), pb.BG)
    for x, value in zip(columns, bodies):
        band[:, x:x + pb.W] = 255
        band[:, x + pb.STRIP:x + pb.W - pb.STRIP] = value
    return band


def test_card_columns_are_centred():
    assert pb.card_columns(3) == [135, 417, 699]
    assert pb.card_columns(2) == [276, 558]          # (1091 - 2*257 - 25) / 2 = 276
    assert pb.card_columns(1) == [417]               # (1091 - 257) / 2 = 417


def test_compose_row_keeping_all_three_is_the_identity():
    band = flat_row()
    assert np.array_equal(pb.compose_row(band, [0, 1, 2]), band)


def test_compose_row_two_tiles_are_centred_with_the_original_gap():
    out = pb.compose_row(flat_row(), [1, 2])
    assert np.array_equal(out, expected_row([276, 558], [20, 30]))


def test_compose_row_single_tile_sits_in_the_middle():
    out = pb.compose_row(flat_row(), [2])
    assert np.array_equal(out, expected_row([417], [30]))


def test_compose_row_follows_the_requested_order():
    out = pb.compose_row(flat_row(), [2, 0])
    assert np.array_equal(out, expected_row([276, 558], [30, 10]))


@pytest.fixture(scope="module")
def original():
    return np.array(Image.open(pb.ORIGINAL).convert("RGB")).astype(int)


def test_measured_geometry_matches_the_original(original):
    for top in pb.ROW_TOP:
        for x in pb.X:
            card = original[top:top + pb.CARD_H, x + pb.STRIP:x + pb.W - pb.STRIP]
            assert (card[[0, -1]] == 255).all()                        # first and last fully white rows
            margins = np.concatenate([original[top + 30:top + pb.CARD_H - 30, x + 2:x + pb.STRIP],
                                      original[top + 30:top + pb.CARD_H - 30, x + pb.W - pb.STRIP:x + pb.W - 2]], axis=1)
            assert (margins == 255).all()                              # no content in the left/right margins
            rows, cols = pb._inside((pb.ROW_TOP.index(top), pb.X.index(x)))
            inside = original[rows, cols]
            assert (inside[:4] == 255).all() and (inside[-4:] == 255).all()   # the swapped inside starts on plain white
            around = original[top + 30:top + pb.CARD_H - 30, [cols.start - 1, cols.stop]]
            assert (around == 255).all()
    assert (original[pb.GAP_TOP - pb.TOP_SHADOW_SHIFT - 10:pb.GAP_TOP - pb.TOP_SHADOW_SHIFT] == pb.BG).all()


def test_reflow_with_the_original_layout_changes_nothing(original):
    same = pb.reflow(original, [pb.DECK, pb.PODCASTS, pb.BONUS], [pb.WRAP_UP, pb.EARLY_ACCESS, pb.TSHIRT])
    assert np.array_equal(same, original)


def test_reflow_without_the_deck(original):
    new = pb.reflow(original, [pb.PODCASTS, pb.BONUS, pb.WRAP_UP], [pb.EARLY_ACCESS, pb.TSHIRT])
    assert new.shape == original.shape
    assert np.array_equal(new[:pb.ROW_TOP[1]], original[:pb.ROW_TOP[1]])        # header and row 1 untouched

    def body(image, tile=None, row=None, x=None):
        if tile:
            row, x = tile[0], pb.X[tile[1]]
        top = pb.ROW_TOP[row]
        return image[top + 10:top + pb.CARD_H - 10, x + pb.STRIP:x + pb.W - pb.STRIP]

    # Row 2 now reads Podcasts, Bonus, Wrap-Up; the deck's icon is nowhere left.
    for col, tile in enumerate([pb.PODCASTS, pb.BONUS, pb.WRAP_UP]):
        assert np.array_equal(body(new, row=1, x=pb.X[col]), body(original, tile))
    # Row 3 holds Early Access and the T-shirt, centred.
    for x, tile in zip(pb.card_columns(2), [pb.EARLY_ACCESS, pb.TSHIRT]):
        assert np.array_equal(body(new, row=2, x=x), body(original, tile))
    # Left and right of the two cards there is only background and shadow, and the picture is symmetric there.
    left_of_cards = new[pb.ROW_TOP[2] + 40:pb.ROW_TOP[2] + pb.CARD_H - 40, :pb.card_columns(2)[0] - 30]
    assert (left_of_cards == pb.BG).all()
    # Outside the cards there is nothing lighter than the background (no white seams) and nothing darker than
    # the darkest shadow of the original (no black bars); far from any card it is plain background.
    outside = np.ones(new.shape[:2], dtype=bool)
    for x in pb.card_columns(2):
        outside[pb.ROW_TOP[2] - 1:pb.ROW_TOP[2] + pb.CARD_H + 1, x:x + pb.W] = False
    region = new[pb.GAP_TOP:][outside[pb.GAP_TOP:]]
    assert region.max() <= pb.BG
    assert region.min() >= original[pb.ROW_TOP[2] + pb.CARD_H + 1:].min()
    assert (new[pb.GAP_TOP:, :90] == pb.BG).all() and (new[pb.GAP_TOP:, -90:] == pb.BG).all()


def test_shadows_between_rows_add_up_to_within_a_few_grey_levels(original):
    """The additive shadow model behind the re-flow: row 2's lower shadow (seen clean below row 3) plus row 3's
    upper shadow (seen clean above row 1) should rebuild the real strip between rows 2 and 3."""
    gap = original[pb.GAP_TOP:pb.ROW_TOP[2]]
    lower = pb.BG - original[pb.GAP_TOP + pb.ROW_STEP:pb.ROW_TOP[2] + pb.ROW_STEP]
    upper = pb.BG - original[pb.GAP_TOP - pb.TOP_SHADOW_SHIFT:pb.ROW_TOP[2] - pb.TOP_SHADOW_SHIFT]
    error = np.abs(gap - (pb.BG - lower - upper))
    assert error.max() <= 6
    assert error.mean() < 1.5
