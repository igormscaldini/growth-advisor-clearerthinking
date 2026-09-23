"""Tests for seo_experiment_analysis.

Two hand-worked cases per estimator (answers computed on paper), then a realistic
synthetic pair: one frame built to be a null, one built to carry a known effect.
"""
import numpy as np
import pandas as pd
import pytest

from seo_experiment_analysis import (
    code_frame,
    code_themes,
    estimate_click_uplift,
    estimate_position_effect,
    impression_weighted_position,
    sentiment,
)


def _dates(n, start="2026-04-01"):
    return pd.date_range(start, periods=n, freq="D")


# ------------------------------------------------- hand-worked: weighted position

def test_weighted_position_hand_case():
    # (4*100 + 10*300) / 400 = (400 + 3000) / 400 = 3400/400 = 8.5
    df = pd.DataFrame({"position": [4.0, 10.0], "impressions": [100, 300]})
    assert impression_weighted_position(df) == pytest.approx(8.5)


def test_weighted_position_equal_weights_is_plain_mean():
    # equal impressions -> (6+8)/2 = 7.0
    df = pd.DataFrame({"position": [6.0, 8.0], "impressions": [50, 50]})
    assert impression_weighted_position(df) == pytest.approx(7.0)


def test_weighted_position_no_impressions_is_nan():
    df = pd.DataFrame({"position": [5.0], "impressions": [0]})
    assert np.isnan(impression_weighted_position(df))


# ------------------------------------------------------ hand-worked: click uplift

def test_click_uplift_recovers_exact_coefficient_noiseless():
    # clicks built to be exactly 10 + 0.02*impressions + 1.0*runs, so OLS must return
    # exactly 1.0 for runs and fit perfectly.
    n = 40
    impressions = np.arange(1000, 1000 + 50 * n, 50, dtype=float)
    runs = np.tile([0.0, 5.0, 10.0, 20.0], n // 4)
    clicks = 10 + 0.02 * impressions + 1.0 * runs
    daily = pd.DataFrame(
        {"clicks": clicks, "impressions": impressions, "runs": runs,
         "position": np.full(n, 8.0)},
        index=_dates(n),
    )
    r = estimate_click_uplift(daily)
    assert r["coef"] == pytest.approx(1.0, abs=1e-8)
    assert r["r_squared"] == pytest.approx(1.0, abs=1e-8)
    assert r["n"] == n


def test_click_uplift_recovers_half_click_per_run():
    # same construction with a 0.5 coefficient: only half of each run converts to a click
    n = 40
    impressions = np.arange(2000, 2000 + 10 * n, 10, dtype=float)
    runs = np.tile([2.0, 4.0, 8.0, 16.0], n // 4)
    clicks = 5 + 0.01 * impressions + 0.5 * runs
    daily = pd.DataFrame(
        {"clicks": clicks, "impressions": impressions, "runs": runs,
         "position": np.full(n, 8.0)},
        index=_dates(n),
    )
    assert estimate_click_uplift(daily)["coef"] == pytest.approx(0.5, abs=1e-8)


def test_click_uplift_zero_when_runs_do_nothing():
    n = 60
    rng = np.random.default_rng(0)
    impressions = rng.uniform(5000, 15000, n)
    daily = pd.DataFrame(
        {"clicks": 0.005 * impressions, "impressions": impressions,
         "runs": rng.uniform(0, 30, n), "position": np.full(n, 8.0)},
        index=_dates(n),
    )
    r = estimate_click_uplift(daily)
    assert r["coef"] == pytest.approx(0.0, abs=1e-6)


# --------------------------------------------------- hand-worked: position effect

def test_position_effect_recovers_known_negative_slope():
    # position = 9 - 0.05*runs exactly -> coefficient must be -0.05
    n = 40
    runs = np.tile([0.0, 10.0, 20.0, 30.0], n // 4)
    daily = pd.DataFrame(
        {"clicks": np.full(n, 50.0), "impressions": np.full(n, 10000.0),
         "runs": runs, "position": 9 - 0.05 * runs},
        index=_dates(n),
    )
    r = estimate_position_effect(daily, lag=0)
    assert r["coef"] == pytest.approx(-0.05, abs=1e-8)


def test_position_effect_respects_lag():
    # position responds only to runs from 3 days earlier
    n = 60
    rng = np.random.default_rng(1)
    runs = rng.uniform(0, 30, n)
    pos = 9 - 0.05 * pd.Series(runs).shift(3).fillna(0).to_numpy()
    daily = pd.DataFrame(
        {"clicks": np.full(n, 50.0), "impressions": np.full(n, 10000.0),
         "runs": runs, "position": pos},
        index=_dates(n),
    )
    lag3 = estimate_position_effect(daily, lag=3)
    lag0 = estimate_position_effect(daily, lag=0)
    assert lag3["coef"] == pytest.approx(-0.05, abs=1e-3)
    assert abs(lag0["coef"]) < 0.02          # wrong lag finds close to nothing
    assert lag3["r_squared"] > lag0["r_squared"]


# ----------------------------------------- realistic synthetic: null and positive

def _realistic(n=150, uplift_clicks=0.0, pos_effect=0.0, seed=7):
    """A frame shaped like the real GSC daily series for the UPT page.

    Weekday seasonality, ~10k impressions/day, ~0.5% CTR, position around 8, and runs
    only on weekdays (Positly batches ran on weekdays).
    """
    rng = np.random.default_rng(seed)
    idx = _dates(n)
    weekday = idx.dayofweek.to_numpy()
    impressions = 10000 * (1 + 0.15 * (weekday < 5)) * rng.lognormal(0, 0.12, n)
    runs = np.where(weekday < 5, rng.poisson(15, n), 0).astype(float)
    base_ctr = 0.005 * rng.lognormal(0, 0.10, n)
    clicks = impressions * base_ctr + uplift_clicks * runs
    position = 8.0 + rng.normal(0, 0.4, n) + pos_effect * runs
    return pd.DataFrame(
        {"clicks": clicks, "impressions": impressions, "runs": runs, "position": position},
        index=idx,
    )


def test_realistic_null_frame_finds_no_click_uplift():
    r = estimate_click_uplift(_realistic(uplift_clicks=0.0))
    assert r["ci_low"] < 0 < r["ci_high"], r        # CI covers zero
    assert r["p_value"] > 0.05


def test_realistic_null_frame_finds_no_position_effect():
    r = estimate_position_effect(_realistic(pos_effect=0.0), lag=0)
    assert r["ci_low"] < 0 < r["ci_high"], r
    assert r["p_value"] > 0.05


def test_realistic_positive_frame_recovers_one_click_per_run():
    r = estimate_click_uplift(_realistic(uplift_clicks=1.0))
    assert r["coef"] == pytest.approx(1.0, abs=0.35), r
    assert r["p_value"] < 0.01
    assert r["ci_low"] > 0


def test_realistic_positive_frame_recovers_position_gain():
    r = estimate_position_effect(_realistic(pos_effect=-0.02), lag=0)
    assert r["coef"] == pytest.approx(-0.02, abs=0.01), r
    assert r["ci_high"] < 0


def test_weekday_confound_does_not_create_a_fake_click_uplift():
    """Runs only happen on weekdays and weekdays have more traffic.

    Without controls that correlation alone would look like an effect; with controls the
    estimator must stay at zero.
    """
    naive = estimate_click_uplift(_realistic(uplift_clicks=0.0), controls=False)
    controlled = estimate_click_uplift(_realistic(uplift_clicks=0.0), controls=True)
    assert naive["p_value"] < 0.05                    # the confound is real
    assert controlled["ci_low"] < 0 < controlled["ci_high"]


# ------------------------------------------------------------------ text coding

@pytest.mark.parametrize("text,theme", [
    ("It was very easy and simple to use", "easy"),
    ("Straightforward and quick", "easy"),
    ("Interesting, made me curious about myself", "interesting"),
    ("Seems like every other personality test out there", "generic"),
    ("pretty standard stuff, nothing special", "generic"),
    ("The questions took too long, one at a time is tedious", "length_concern"),
    ("Felt thorough and scientific", "depth_accuracy"),
    ("just some more click bait, they will charge you for results", "skeptical"),
    ("The layout looks clean and modern", "design_visual"),
    ("The wording was confusing and the options were limited", "confusing"),
])
def test_theme_coder_hits(text, theme):
    assert code_themes(text)[theme] is True


@pytest.mark.parametrize("text,theme", [
    ("It was not easy to answer", "easy"),
    ("Honestly it wasn't interesting at all", "interesting"),
    ("boring and repetitive", "interesting"),
    ("The questions asked about my social life", "design_visual"),
    ("The results were not accurate", "depth_accuracy"),
])
def test_theme_coder_negation_and_misses(text, theme):
    assert code_themes(text)[theme] is False


def test_topic_themes_fire_regardless_of_valence():
    """generic/skeptical/design/confusing are topic codes, not valence codes.

    "Nothing about the design stood out" is still an answer *about* the design; the
    valence lives in `sentiment`, not in the theme flag.
    """
    assert code_themes("Nothing about the design stood out to me")["design_visual"] is True
    assert sentiment("Nothing about the design stood out to me") <= 0


def test_answer_can_carry_several_themes():
    t = code_themes("Easy to use but it seems like a pretty standard personality test")
    assert t["easy"] and t["generic"]


@pytest.mark.parametrize("text,expected", [
    ("Easy, interesting and good", 1),
    ("Boring and confusing", -1),
    ("It was not interesting", -1),
    ("A personality test", 0),
    ("", 0),
])
def test_sentiment(text, expected):
    assert sentiment(text) == expected


@pytest.mark.parametrize("text", [
    "It looks like a standard personality test.",
    "It seemed like a standard personality test.",
    "It seems like other personality tests. They tend to ask similar questions.",
    "It seemed like a survey I do on Mturk",
    "Seems like a normal test with questions about how I interact with people.",
])
def test_comparison_like_is_not_praise(text):
    """"seems like a standard test" is a verdict of sameness, not a compliment."""
    assert sentiment(text) == 0


@pytest.mark.parametrize("text", [
    "I like that I didn't need to click through a lot of ads",
    "I liked the questions",
])
def test_preference_like_still_counts_as_positive(text):
    assert sentiment(text) == 1


def test_negation_scopes_over_the_whole_clause():
    # both "valid" and "accurate" sit after the negator and must both flip
    assert sentiment("It didn't seem very valid or accurate like an MMPI would be") == -1


def test_clause_boundary_stops_negation():
    # the negation belongs to the first clause only; "interesting" must stay positive
    assert sentiment("It was not boring, it was interesting and useful") == 1


# Real answers drawn at random from the export and hand-coded by reading them, kept as a
# regression guard: an early version of the coder scored the "seems like a standard test"
# family as positive and only agreed with the hand codes on 70% of a 50-answer sample.
GOLDEN = [
    ("I thought it was fun and interesting.", 1),
    ("Interesting and easy to understand. It seemed thoughtful and clear. Simple but insightful.", 1),
    ("It looks like a standard personality test.", 0),
    ("It seemed like a standard personality test.", 0),
    ("It seems like other personality tests.  They tend to ask similar questions.", 0),
    ("Questions seemed to focus on extrovert versus introvert", 0),
    ("I thought it was pretty generic and that the overall design looked somewhat like spam content.", -1),
    ("It seems superficial", -1),
    ("I hate it.", -1),
    ("It seems pretty long.", -1),
    ("Biased based on cookies", -1),
    ("The test was unexpectedly good", 1),
    ("The design is very minimalistic but I like that I didn't need to click through a lot of ads to start the test.", 1),
    ("It didn't seem very valid or accurate like an MMPI would be for example.", -1),
    ("I have taken this test before and I know what I am.", 0),
    ("Easy questions, a fair variety of choices for answers", 1),
]


@pytest.mark.parametrize("text,expected", GOLDEN)
def test_sentiment_matches_hand_coding_on_real_answers(text, expected):
    assert sentiment(text) == expected


def test_generic_theme_catches_the_sameness_verdicts():
    """The headline qualitative finding is "it looks like every other test"."""
    for text, _ in GOLDEN[2:5]:
        assert code_themes(text)["generic"] is True


def test_code_frame_shape_and_index():
    s = pd.Series(["easy and fun", "generic junk", ""], index=[10, 11, 12])
    out = code_frame(s)
    assert list(out.index) == [10, 11, 12]
    assert out.loc[10, "easy"] and out.loc[10, "sentiment"] == 1
    assert out.loc[11, "generic"]
    assert out.loc[12, "sentiment"] == 0


@pytest.mark.parametrize("text", [
    "It seems authentic and the questions are not too hard to answer.",
    "The questions were not confusing at all",
    "Nothing weird about it",
])
def test_confusing_theme_ignores_the_negated_form(text):
    assert code_themes(text)["confusing"] is False
