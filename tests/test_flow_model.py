"""Tests for flow_model.py: the page rules (evaluated in Python exactly as they are compiled for GA4),
source grouping and the snapshot block shape. Hand-worked answers on synthetic rows."""
import flow_model as fm


# --- page categories: one real page of each kind from the Oct 14 to Nov 12, 2026 pull ------------
def test_page_category_on_real_landing_pages():
    cases = {
        ("www.clearerthinking.org", "/"): "Home",
        ("www.clearerthinking.org", "/home"): "Home",
        ("www.clearerthinking.org", "/post/should-you-steelman-people-you-disagree-with"): "Articles",
        ("programs.clearerthinking.org", "/post/discover-your-philosophical-beliefs-with-our-new-quiz"): "Articles",
        ("programs.clearerthinking.org", "/who_attracts_you_study.html"): "Tools",
        ("www.clearerthinking.org", "/who_attracts_you_study.html"): "Tools",   # the www copy of the study
        ("programs.clearerthinking.org", "/personality-test.html"): "Tools",
        ("programs.clearerthinking.org", "/"): "Tools",                          # redirects to the tools gallery
        ("www.clearerthinking.org", "/clearer-thinking-tools"): "Tools",
        ("programs.clearerthinking.org", "/unique-traits-test"): "Tools",
        ("programs.clearerthinking.org", "/cognitive-test-intro.html"): "Tools",
        ("www.clearerthinking.org", "/coaching"): "Other",
        ("programs.clearerthinking.org", "/coaching"): "Other",
        ("www.clearerthinking.org", "/plus"): "Other",
        ("podcast.clearerthinking.org", "/"): "Other",                           # not the www homepage
        ("programs.clearerthinking.org", "/mailing-list/unsubscribe"): "Other",
        ("programs.clearerthinking.org", "/dashboard.html"): "Other",
        ("programs.clearerthinking.org", "/unanswered-questions-in-psychology/"): "Other",
    }
    for (host, path), want in cases.items():
        assert fm.page_category(host, path) == want, (host, path)


def test_sessions_without_a_landing_page_are_not_web_visits():
    assert fm.page_category("(not set)", "(not set)") is None      # the email-open pixel
    assert fm.page_category("", "") is None                        # server-side purchase events
    assert fm.page_category("programs.clearerthinking.org", "(not set)") is None  # first hit not a page view


def test_categories_are_disjoint_and_exhaustive_for_web_paths():
    pages = [("www.clearerthinking.org", p) for p in ("/", "/post/x", "/coaching", "/clearer-thinking-tools", "/plus", "/about")]
    pages += [("programs.clearerthinking.org", p) for p in ("/", "/post/x", "/coaching", "/personality-test.html", "/mailing-list/x")]
    for host, path in pages:
        hits = [name for name, expr in fm.PAGE_CATEGORIES.items() if fm.matches(expr, host, path)]
        assert len(hits) == 1, (host, path, hits)


def test_rule_tree_compiles_to_ga4_filters():
    pytest = __import__("pytest")
    pytest.importorskip("google.analytics.data_v1beta")
    f = fm.to_ga4_filter(fm.TOOLS)
    assert f.and_group.expressions[0].filter.field_name == "landingPage"        # WEB leaf first
    assert f.and_group.expressions[1].not_expression.and_group               # NOT HOME
    assert f.and_group.expressions[3].or_group.expressions[0].filter.string_filter.value == "who_attracts_you"


# --- source grouping -----------------------------------------------------------------------------
def test_fold_sources_sums_channels_into_fixed_groups():
    rows = [
        {"firstUserDefaultChannelGroup": "Paid Search", "totalUsers": 200},
        {"firstUserDefaultChannelGroup": "Display", "totalUsers": 7574},
        {"firstUserDefaultChannelGroup": "Cross-network", "totalUsers": 4477},
        {"firstUserDefaultChannelGroup": "Organic Social", "totalUsers": 5078},
        {"firstUserDefaultChannelGroup": "Organic Video", "totalUsers": 418},
        {"firstUserDefaultChannelGroup": "Unassigned", "totalUsers": 9},
        {"firstUserDefaultChannelGroup": "Direct", "totalUsers": 1},
    ]
    assert fm.fold_sources(rows) == {"Paid Media": 12251, "Social": 5496, "Other": 9, "Direct": 1}
    assert all(s in fm.SOURCE_ORDER for s in fm.fold_sources(rows))


# --- snapshot block ------------------------------------------------------------------------------
def test_flow_block_orders_pages_and_drops_zero_rows():
    landing = {"Tools": {"Direct": 100, "Email": 0, "Organic Search": 40}, "Home": {"Direct": 10}}
    outcomes = {"Tools": {"Email Submitted": {"Direct": 30, "Organic Search": 12}, "CT+ Sign Up": {"Direct": 1}}}
    b = fm.flow_block(landing, outcomes)
    assert [r["page"] for r in b["landing"]] == ["Home", "Tools", "Tools"]
    assert b["landing"][1] == {"source": "Direct", "page": "Tools", "users": 100}
    assert {(r["outcome"], r["source"]): r["users"] for r in b["outcomes"]} == {
        ("Email Submitted", "Direct"): 30, ("Email Submitted", "Organic Search"): 12, ("CT+ Sign Up", "Direct"): 1}
