"""Tests for the top-tools ranking (reports/top_tools_ranking_2026-11-19_src): the page rules, the ranking and the page."""
import importlib.util
import random
import sys
from datetime import date, datetime
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "reports/top_tools_ranking_2026-11-19_src"
sys.path.insert(0, str(SRC))


def _load(name):
    spec = importlib.util.spec_from_file_location(f"top_tools_{name}", SRC / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


R, fetch, page = _load("ranking"), _load("fetch_data"), _load("build_page")

BASES = {"/personality-test", "/how_rational_are_you_really_take_the_test", "/unique-traits-test",
         "/artificial_intelligence_quiz", "/cognitive_defusion", "/understanding-your-morality"}


# ---- which page belongs to which tool ----

def test_every_spelling_of_a_tool_page_is_the_tool():
    for path in ("/unique-traits-test", "/unique-traits-test/", "/unique-traits-test/index.html", "/Unique-Traits-Test.html"):
        assert R.classify(path, BASES) == ("/unique-traits-test", "own")
    assert R.classify("/Cognitive_Defusion/", BASES) == ("/cognitive_defusion", "own")


def test_sub_paths_and_old_addresses_count_but_lookalikes_do_not():
    assert R.classify("/understanding-your-morality/report/", BASES) == ("/understanding-your-morality", "own")
    assert R.classify("/personality.html", BASES) == ("/personality-test", "own")          # old address
    assert R.classify("/personality-test-pdf-generator/", BASES) is None                   # another page
    assert R.classify("/personality_report.html", BASES) is None                           # report page
    assert R.classify("/rationality-report/skeptic.html", BASES) is None
    assert R.classify("/dashboard.html", BASES) is None
    assert R.classify("/", BASES) is None


def test_partner_copies_are_told_apart():
    assert R.classify("/p/bluedot/artificial-intelligence-quiz/", BASES) == ("/artificial_intelligence_quiz", "partner")
    assert R.classify("/p/asimov-press/rationality-test/", BASES) == ("/how_rational_are_you_really_take_the_test", "partner")
    assert R.classify("/p/x/artificial-intelligence-quiz/short/index.html", BASES) == ("/artificial_intelligence_quiz", "partner")
    assert R.classify("/p/company-x/brand-cta-test/", BASES) is None                       # copy of no listed tool
    assert R.classify("/p/bluedot/biosafety-quiz/", BASES) is None                         # tool not in this list


def test_tools_from_cards_keeps_only_the_tools_host():
    tools, elsewhere = R.tools_from_cards([
        ("The Ultimate Personality Test", "https://programs.clearerthinking.org/personality-test.html"),
        ("Step Back From Your Thoughts", "https://programs.clearerthinking.org/Cognitive_Defusion"),
        ("Society Explained", "https://society.clearerthinking.org/"),
    ])
    assert set(tools) == {"/personality-test", "/cognitive_defusion"}
    assert tools["/cognitive_defusion"]["url"].endswith("/Cognitive_Defusion")
    assert elsewhere == ["Society Explained"]


def test_excluded_tools_are_not_ranked():
    cards = [("Who Attracts You?", "https://programs.clearerthinking.org/who_attracts_you_study.html"),
             ("Cognitive Assessment (Only Free For Supporters)", "https://programs.clearerthinking.org/cognitive-test-intro.html"),
             ("The Ultimate Personality Test", "https://programs.clearerthinking.org/personality-test.html")]
    assert set(R.tools_from_cards(cards)[0]) == {"/personality-test"}
    assert set(R.tools_from_cards(cards, excluded={})[0]) == {"/personality-test", "/who_attracts_you_study", "/cognitive-test-intro"}
    # their pages then belong to no ranked tool
    assert R.classify("/who_attracts_you_study.html", {"/personality-test"}) is None


# ---- synthetic set 1, worked by hand: grouping and bounds ----

def test_group_and_bounds_by_hand():
    rows = [("/unique-traits-test", 40), ("/unique-traits-test/", 60), ("/personality-test.html", 500),
            ("/personality.html", 30), ("/p/bluedot/artificial-intelligence-quiz/", 900),
            ("/artificial_intelligence_quiz.html", 7), ("/dashboard.html", 10_000)]
    g = R.group_paths(rows, BASES)
    assert g["/unique-traits-test"]["own"] == {"/unique-traits-test": 40, "/unique-traits-test/": 60}
    assert g["/artificial_intelligence_quiz"] == {"own": {"/artificial_intelligence_quiz.html": 7},
                                                  "partner": {"/p/bluedot/artificial-intelligence-quiz/": 900}}
    # 40 and 60 visitors of two spellings: at least 60 people (all 40 are among the 60), at most 100 (nobody in both)
    assert R.bounds(g["/unique-traits-test"]["own"]) == (60, 100)
    assert R.bounds(g["/personality-test"]["own"]) == (500, 530)
    assert R.bounds(g["/cognitive_defusion"]["own"]) == (0, 0)
    assert "/dashboard.html" not in str(g)                                                 # the biggest page is no tool


# ---- synthetic set 2, worked by hand: ranking, ties, certainty ----

def test_rank_by_hand_with_a_tie():
    users = {"/c": 50, "/a": 50, "/b": 900, "/d": 3}
    assert R.rank(users, 3) == [("/b", 900), ("/a", 50), ("/c", 50)]
    assert R.rank(users, 10) == [("/b", 900), ("/a", 50), ("/c", 50), ("/d", 3)]


def test_ranking_is_certain_only_when_the_rest_cannot_reach_the_top():
    exact = {"/a": 100, "/b": 80, "/c": 60}
    assert R.ranking_is_certain(exact, {"/d": 59, "/e": 10}, n=3)
    assert R.ranking_is_certain(exact, {"/d": 60}, n=3)            # could only tie the last place
    assert not R.ranking_is_certain(exact, {"/d": 61}, n=3)        # an uncounted tool could be third
    assert R.ranking_is_certain(exact, {"/d": 70}, n=2)
    assert not R.ranking_is_certain(exact, {"/d": 1}, n=5)         # fewer exact counts than places
    assert R.pick_candidates({"/a": 5, "/b": 9, "/c": 9, "/d": 1}, n=1, extra=1) == ["/b", "/c"]


# ---- realistic synthetic sets: 96 tools shaped like the GA4 page report ----

def _report(users_of):
    """GA4-like rows: every tool under two spellings that share no visitors, plus pages that belong to no tool."""
    rows = [("/dashboard.html", 10_429), ("/mailing-list/unsubscribe/", 7_632), ("/personality_report.html", 34_360)]
    for base, users in users_of.items():
        rows += [(base + ".html", users - users // 3), (base + "/", users // 3)]
    return rows


def _exact_ranking(rows, bases, variant_kinds=("own",)):
    grouped = R.group_paths(rows, bases)
    # the two spellings share no visitors by construction, so the exact count is the sum
    return R.rank({b: sum(u for k in variant_kinds for u in grouped[b][k].values()) for b in bases}, 10)


def test_null_set_all_tools_equal_gives_no_order_but_the_alphabet():
    bases = {f"/tool_{i:02d}" for i in range(96)}
    rows = _report({b: 1_200 for b in bases})
    random.Random(7).shuffle(rows)
    top = _exact_ranking(rows, bases)
    assert [u for _, u in top] == [1_200] * 10
    assert [b for b, _ in top] == sorted(bases)[:10]


def test_planted_order_is_recovered_whatever_the_row_order():
    bases = {f"/tool_{i:02d}" for i in range(96)}
    users_of = {b: 100 + 37 * int(b[-2:]) for b in bases}          # tool_95 biggest, tool_00 smallest
    expected = [(f"/tool_{i:02d}", 100 + 37 * i) for i in range(95, 85, -1)]
    for seed in (1, 2, 3):
        rows = _report(users_of)
        random.Random(seed).shuffle(rows)
        assert _exact_ranking(rows, bases) == expected
    # a partner copy changes the order only when partner copies are counted
    rows = _report(users_of) + [("/p/bluedot/tool-00/", 50_000)]
    assert _exact_ranking(rows, bases) == expected
    assert _exact_ranking(rows, bases, ("own", "partner"))[0] == ("/tool_00", 50_100)


# ---- windows ----

def test_windows_end_on_the_last_full_day():
    w = fetch.windows(date(2026, 11, 18))
    assert w["12m"] == (date(2025, 11, 19), date(2026, 11, 18))
    assert w["ytd"] == (date(2026, 1, 1), date(2026, 11, 18))
    assert w["90d"] == (date(2026, 8, 21), date(2026, 11, 18))
    assert (w["90d"][1] - w["90d"][0]).days + 1 == 90


# ---- the page ----

def _data():
    tools = {f"/t{i}": {"name": f"Tool {i}", "url": f"https://programs.clearerthinking.org/t{i}.html",
                        "description": f"Sentence one about tool {i}. Sentence two.", "launch_date": "2020-01-01"}
             for i in range(12)}
    tools["/t3"]["launch_date"] = "2026-03-19"
    tools["/t5"]["description"] = "Get a custome report with no full stop"
    counts = {f"/t{i}": {"own": {"users": 1000 * (i + 1), "lower": 0, "upper": 0, "pages": 1},
                         "with_partner": {"users": 1000 * (i + 1) + (50_000 if i == 0 else 0), "lower": 0, "upper": 0, "pages": 1}}
              for i in range(12)}
    return {"host": "programs.clearerthinking.org", "top_n": 10, "tools": tools, "elsewhere": [],
            "excluded": ["Tool X", "the Tool Y"],
            "windows": {"12m": {"start": "2025-11-19", "end": "2026-11-18", "tools": counts,
                                "certain": {"own": True, "with_partner": True}}}}


def test_page_rows_follow_the_ranking_and_the_variant():
    rows = page.top_rows(_data(), "12m", "own")
    assert [r["name"] for r in rows] == [f"Tool {i}" for i in range(11, 1, -1)]
    assert [r["users"] for r in rows][:2] == [12_000, 11_000]
    assert {r["name"]: r["tag"] for r in rows}["Tool 3"] == "New in 2026"
    assert sum(bool(r["tag"]) for r in rows) == 1
    with_partner = page.top_rows(_data(), "12m", "with_partner")
    assert (with_partner[0]["name"], with_partner[0]["users"]) == ("Tool 0", 51_000)


def test_first_sentence():
    assert page.first_sentence("Find your type.  Also, get a report!") == "Find your type."
    assert page.first_sentence("Get a custome report with no full stop") == "Get a custom report with no full stop."
    assert page.first_sentence("Compare your values to others', with this quiz") == "Compare your values to others', with this quiz."
    assert page.first_sentence("") == ""


def test_rendered_page():
    out = page.render(_data(), "12m", "own", now=datetime(2026, 11, 19, 15, 5))
    assert out.count('<span class="rank">') == 10
    assert out.index("Tool 11") < out.index("Tool 10") < out.index("Tool 2<")
    assert "12,000" in out and "Tool 1<" not in out
    assert "Ranked by unique users, Nov 19, 2025 to Nov 18, 2026. Updated 2026-11-19 03:05pm." in out
    assert "Partner-branded copies of a tool are not counted. Not ranked: Tool X and the Tool Y." in out
    assert "count toward that tool" in page.render(_data(), "12m", "with_partner")
    assert "—" not in out and "–" not in out                # no em or en dashes
