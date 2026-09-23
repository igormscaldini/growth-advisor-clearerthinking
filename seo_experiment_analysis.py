"""Analysis helpers for the GuidedTrack program "UPT - SEO Experiment" (program 31723).

The experiment sent Positly panellists to Google, told them to search the exact phrase
"personality test", find the Clearer Thinking Ultimate Personality Test in the results,
answer its first three questions and then describe their first impression.

Two questions can be answered from the data:

1. Did participants really do it?  Every genuine run should leave one impression + one
   click on the exact query "personality test" for
   https://programs.clearerthinking.org/personality-test.html in Search Console.
   `estimate_click_uplift` regresses daily clicks on daily run count (controlling for
   impressions and day of week); the coefficient is "extra GSC clicks per run".

2. Did the clicks move the ranking?  `estimate_position_effect` regresses daily average
   position on the run count at a lag.  A negative coefficient means better rank.

The text helpers code the open-ended answers into themes and a sentiment score.
Everything here is pure: callers pass frames in, no I/O.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
import statsmodels.api as sm

TARGET_PAGE = "https://programs.clearerthinking.org/personality-test.html"
TARGET_QUERY = "personality test"
PROGRAM_ID = 31723


# --------------------------------------------------------------------------- metrics

def impression_weighted_position(df: pd.DataFrame) -> float:
    """Average GSC position weighted by impressions.

    A plain mean over days is wrong: a day with 10 impressions would count as much as a
    day with 100,000.  Returns nan when there are no impressions.
    """
    imp = df["impressions"].sum()
    if imp == 0:
        return float("nan")
    return float((df["position"] * df["impressions"]).sum() / imp)


def _design(daily: pd.DataFrame, regressor: pd.Series, controls: bool) -> pd.DataFrame:
    x = pd.DataFrame({"runs": regressor.astype(float)})
    if controls:
        x["impressions"] = daily["impressions"].astype(float)
        dow = pd.get_dummies(daily.index.dayofweek, prefix="dow", drop_first=True)
        dow.index = daily.index
        x = x.join(dow.astype(float))
    return sm.add_constant(x, has_constant="add")


def _fit(y: pd.Series, x: pd.DataFrame) -> dict:
    ok = x.notna().all(axis=1) & y.notna()
    model = sm.OLS(y[ok].astype(float), x[ok]).fit()
    lo, hi = model.conf_int().loc["runs"]
    return {
        "coef": float(model.params["runs"]),
        "ci_low": float(lo),
        "ci_high": float(hi),
        "p_value": float(model.pvalues["runs"]),
        "n": int(ok.sum()),
        "r_squared": float(model.rsquared),
    }


def estimate_click_uplift(daily: pd.DataFrame, controls: bool = True) -> dict:
    """Extra GSC clicks per experiment run, from a daily OLS.

    `daily` is indexed by date with columns clicks, impressions, position, runs.
    A coefficient near 1.0 means each run produced roughly one real search click.
    """
    return _fit(daily["clicks"], _design(daily, daily["runs"], controls))


def estimate_position_effect(daily: pd.DataFrame, lag: int = 0, controls: bool = True) -> dict:
    """Effect of runs `lag` days earlier on average position (negative = better rank)."""
    return _fit(daily["position"], _design(daily, daily["runs"].shift(lag), controls))


# ----------------------------------------------------------------------------- text

# Each theme is (positive patterns, blocking patterns).  Patterns are regexes matched
# against the lower-cased answer.  A theme fires when a positive pattern matches and no
# blocking pattern matches, which is what keeps "not very easy" out of the EASY bucket.
_NEG = r"(?:not|n't|isn't|wasn't|hardly|never|far from)\s+(?:\w+\s+){0,2}"

THEMES: dict[str, tuple[list[str], list[str]]] = {
    "easy": ([r"\beasy\b", r"\bsimple\b", r"\bstraight ?forward\b", r"\bquick\b",
              r"\beasily\b", r"\bclear\b", r"\bintuitive\b", r"\bsmooth\b"],
             [_NEG + r"(?:easy|simple|clear|quick)"]),
    "interesting": ([r"\binterest", r"\bengaging\b", r"\bfun\b", r"\bcurious\b",
                     r"\bcuriosity\b", r"\benjoy", r"\bintrigu", r"\bcool\b"],
                    [_NEG + r"(?:interest|fun|engaging)", r"\bnot interesting\b",
                     r"\bboring\b", r"\buninterest"]),
    "generic": ([r"\bgeneric\b", r"\btypical\b", r"\bstandard\b", r"\bsimilar to\b",
                 r"\blike (?:any |every |most |all )?other\b", r"\bnothing special\b",
                 r"\brun.of.the.mill\b", r"\bsame as\b", r"\bbasic\b", r"\bordinary\b",
                 r"\bnothing new\b", r"\bcookie.cutter\b", r"\baverage\b"], []),
    "length_concern": ([r"\btoo long\b", r"\blong time\b", r"\btakes? (?:a )?(?:too )?long\b",
                        r"\btedious\b", r"\bdrawn out\b", r"\bone (?:question )?at a time\b",
                        r"\bmany questions\b", r"\blengthy\b", r"\btoo many\b",
                        r"\bslow(?:ly)?\b", r"\btime consuming\b"], []),
    "depth_accuracy": ([r"\bthorough\b", r"\bin.depth\b", r"\bdetailed\b", r"\baccurate\b",
                        r"\bscientific\b", r"\bthoughtful\b", r"\bwell.(?:designed|written|thought)\b",
                        r"\bcomprehensive\b", r"\bnuanced\b", r"\binsightful\b", r"\bprofessional\b"],
                       [_NEG + r"(?:accurate|thorough|scientific)", r"\binaccurate\b"]),
    "skeptical": ([r"\bclick ?bait\b", r"\bscam\b", r"\bsketch", r"\bskeptic", r"\bsuspicious\b",
                   r"\bpay\b", r"\bcharge\b", r"\bmoney\b", r"\bsell\b", r"\bad(?:s|vert)",
                   r"\bmy (?:data|information|email)\b", r"\bemail address\b", r"\bspam\b",
                   r"\bdistrust\b", r"\bnot (?:sure|convinced) (?:if|it|that)\b",
                   r"\bdoubt", r"\bgimmick\b"], []),
    "design_visual": ([r"\bdesign", r"\blayout\b", r"\bvisual", r"\bclean\b", r"\bcolou?rful\b",
                       r"\blook(?:s|ed)? (?:nice|good|great|clean|professional|modern)\b",
                       r"\bmodern\b", r"\bwell laid out\b", r"\buser.friendly\b",
                       r"\binterface\b", r"\bgraphics?\b"], []),
    "confusing": ([r"\bconfus", r"\bunclear\b", r"\bvague\b", r"\bhard to (?:answer|understand|tell)\b",
                   r"\bdifficult to (?:answer|understand)\b", r"\bambiguous\b", r"\brepetitive\b",
                   r"\bodd\b", r"\bweird\b", r"\bstrange\b", r"\blimited (?:answer|option|choice)",
                   r"\bnot enough (?:answer|option|choice)"],
                  # "not too hard to answer" / "wasn't confusing" are the opposite verdict
                  [r"(?:not|n't|nothing)\s+(?:too\s+|that\s+|very\s+|so\s+)?(?:hard|difficult|confus|unclear|vague|weird|odd|strange)"]),
}

_POS_WORDS = {
    "easy", "interesting", "good", "great", "nice", "fun", "enjoyed", "enjoy", "engaging",
    "simple", "clear", "accurate", "thorough", "insightful", "helpful", "curious", "cool",
    "intriguing", "thoughtful", "professional", "quick", "straightforward", "liked", "like",
    "love", "loved", "excellent", "impressive", "impressed", "relatable", "relevant",
    "useful", "pleasant", "positive", "better", "best", "smooth", "friendly", "valid",
    "solid", "legit", "informative", "polished", "appealing", "fine",
}
_NEG_WORDS = {
    "boring", "bad", "poor", "confusing", "confused", "vague", "generic", "clickbait",
    "scam", "sketchy", "suspicious", "tedious", "annoying", "dislike", "disliked", "bland",
    "shallow", "inaccurate", "useless", "weird", "odd", "strange", "repetitive", "long",
    "slow", "limited", "meh", "skeptical", "gimmick", "disappointing", "disappointed",
    "frustrating", "worse", "worst", "unclear", "doubtful", "silly", "hate", "hated",
    "superficial", "biased", "spam", "invasive", "pointless", "lame", "dull", "creepy",
    "intrusive", "simplistic", "doubt", "sceptical", "unnecessary", "clunky",
}
_NEGATORS = {"not", "no", "never", "none", "dont", "didnt", "wasnt", "isnt", "hardly",
             "barely", "nothing", "without"}

# "like" is a preference only in "I like"; in "seems like", "looks somewhat like" and
# "like any other test" it is a comparison. Those uses are stripped before scoring,
# otherwise every "seems like a standard test" answer reads as praise — which is
# precisely the population whose verdict matters most here.
_COMPARISON_LIKE = [
    re.compile(r"\b(?:seem|look|feel|felt|sound|act|read|come|came)\w*\s+(?:\w+\s+){0,2}like\b"),
    re.compile(r"\b(?:just|is|was|were|are|much|more|somewhat|exactly|basically)\s+like\b"),
    re.compile(r"\blike\s+(?:any|every|most|all|other|others|another|an?|the|many|some|a\s+lot)\b"),
]

_CLAUSE_SPLIT = re.compile(r"[.;,!?]+|\bbut\b|\byet\b|\bthough\b|\balthough\b|\bhowever\b")


def code_themes(text: str) -> dict[str, bool]:
    """Which themes a free-text answer touches.  Answers can carry several."""
    t = (text or "").lower()
    out = {}
    for name, (pos, block) in THEMES.items():
        hit = any(re.search(p, t) for p in pos) and not any(re.search(b, t) for b in block)
        out[name] = bool(hit)
    return out


def sentiment(text: str) -> int:
    """Crude polarity of an answer: +1 positive, 0 mixed/neutral, -1 negative.

    Negation is scoped to the clause: once a negator appears, every sentiment word after
    it in that clause flips, so "it didn't seem very valid or accurate" scores negative
    on both words rather than only on the one next to the negator. Clauses break on
    punctuation and on but/yet/though/however, which is where the polarity usually turns.
    """
    t = (text or "").lower()
    for pat in _COMPARISON_LIKE:
        t = pat.sub(" ", t)
    score = 0
    for clause in _CLAUSE_SPLIT.split(t):
        negated = False
        for w in re.findall(r"[a-z']+", clause):
            if w in _NEGATORS or w.endswith("n't"):
                negated = True
                continue
            val = 1 if w in _POS_WORDS else (-1 if w in _NEG_WORDS else 0)
            if val:
                score += -val if negated else val
    return 1 if score > 0 else (-1 if score < 0 else 0)


def code_frame(answers: pd.Series) -> pd.DataFrame:
    """Theme flags + sentiment for a series of free-text answers."""
    themes = pd.DataFrame([code_themes(t) for t in answers], index=answers.index)
    themes["sentiment"] = [sentiment(t) for t in answers]
    return themes
