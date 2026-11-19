"""Pure-function tests for related_posts.py (no network). Expected values are worked out by hand in the comments."""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import related_posts as rp  # noqa: E402

# Symmetric similarity for four articles: everything is most like article 0.
#        0    1    2    3
SIM = [[0.0, 0.9, 0.8, 0.7],
       [0.9, 0.0, 0.3, 0.2],
       [0.8, 0.3, 0.0, 0.1],
       [0.7, 0.2, 0.1, 0.0]]
EVERYONE = {s: [0, 1, 2, 3] for s in range(4)}


def test_tokens_drops_stopwords_short_words_and_house_words():
    assert rp.tokens("The Gambler's Fallacy is NOT always a fallacy; click here to read") == ["gambler's", "fallacy", "always", "fallacy"]
    assert rp.tokens("") == []


def test_tfidf_by_hand():
    # idf = ln((1+3)/(1+df)) + 1 -> cat (df 2) 1.28768, dog and fish (df 1) 1.69315
    # doc 0 = [cat, dog]: norm = sqrt(1.28768^2 + 1.69315^2) = 2.12718 -> cat 0.60535, dog 0.79596
    v = rp.tfidf([["cat", "dog"], ["cat"], ["fish"]])
    assert v[0]["cat"] == pytest.approx(0.60535, abs=1e-4) and v[0]["dog"] == pytest.approx(0.79596, abs=1e-4)
    assert v[1] == {"cat": pytest.approx(1.0)} and v[2] == {"fish": pytest.approx(1.0)}
    assert rp.tfidf([[]]) == [{}]


def test_cosine_all_by_hand_and_symmetric():
    sim = rp.cosine_all(rp.tfidf([["cat", "dog"], ["cat"], ["fish"]]))
    assert sim[0][1] == pytest.approx(0.60535, abs=1e-4) == sim[1][0]      # only "cat" is shared
    assert sim[0][2] == 0 and sim[1][2] == 0                               # nothing shared with the fish document
    assert sim[0][0] == 0                                                   # the diagonal is never filled: no self links


def test_sublinear_term_frequency():
    # "cat" three times: tf weight 1 + ln 3 = 2.0986, not 3
    v = rp.tfidf([["cat", "cat", "cat", "dog"], ["dog"]])
    idf_cat, idf_dog = math.log(3 / 2) + 1, math.log(3 / 3) + 1
    cat, dog = (1 + math.log(3)) * idf_cat, idf_dog
    assert v[0]["cat"] == pytest.approx(cat / math.hypot(cat, dog))


def test_assign_respects_the_cap():
    # k=1, cap=2. Most-similar-first: 0->1, 1->0, 2->0 (0 now at the cap), so 3 cannot have 0 and takes 1.
    assert rp.assign(SIM, EVERYONE, k=1, cap=2, min_in=0) == {0: [1], 1: [0], 2: [0], 3: [1]}


def test_assign_lifts_articles_nobody_chose():
    # k=1, cap=3: first pass gives 0->1, 1->0, 2->0, 3->0, leaving 2 and 3 with no inbound link.
    # Lift 2: its best source 0 cannot spare its only link (1 has just one inbound), so 1 swaps 0 for 2.
    # Lift 3: 0 and 1 cannot spare, so 2 swaps 0 for 3. Everyone ends with exactly one inbound link.
    got = rp.assign(SIM, EVERYONE, k=1, cap=3, min_in=1)
    assert got == {0: [1], 1: [2], 2: [3], 3: [0]}
    assert sorted(t for ts in got.values() for t in ts) == [0, 1, 2, 3]


def test_assign_never_links_below_the_floor():
    # floor 0.25 leaves only the pairs 0-1, 0-2, 0-3 and 1-2. Article 3's sole allowed source is 0, whose one
    # link cannot be spared, so 3 stays without an inbound link instead of getting an unrelated one.
    got = rp.assign(SIM, EVERYONE, k=1, cap=3, min_in=1, floor=0.25)
    assert got == {0: [1], 1: [2], 2: [0], 3: [0]}
    assert all(SIM[s][t] >= 0.25 for s, ts in got.items() for t in ts)


def test_assign_only_uses_each_sources_own_candidates():
    # Article 0 may link only to 2, although 1 is its closest match.
    got = rp.assign(SIM, {0: [2], 1: [0, 2, 3], 2: [0, 1, 3], 3: [0, 1, 2]}, k=1, cap=3, min_in=0)
    assert got == {0: [2], 1: [0], 2: [0], 3: [0]}


def test_assign_orders_each_list_by_similarity_and_skips_self():
    got = rp.assign(SIM, EVERYONE, k=3, cap=9, min_in=0)
    assert got[0] == [1, 2, 3] and got[3] == [0, 1, 2]
    assert all(s not in ts for s, ts in got.items())
    assert rp.assign(SIM, {}) == {}


def test_blend_and_headings_and_glossary():
    assert rp.blend([[0.0, 1.0]], [[1.0, 0.0]], 0.6) == [[pytest.approx(0.4), pytest.approx(0.6)]]
    doc = {"nodes": [{"type": "HEADING", "nodes": [{"textData": {"text": "Why it matters"}}]},
                     {"type": "PARAGRAPH", "nodes": [{"textData": {"text": "body text"}}]},
                     {"type": "HEADING", "nodes": [{"textData": {"text": "What to do"}}]}]}
    assert rp.headings(doc) == "Why it matters What to do"
    assert rp.headings(None) == ""
    assert rp.is_glossary("impact-bias-definition-examples-and-effects") and not rp.is_glossary("what-makes-something-a-cult")


def test_eligible_excludes_hub_redirected_and_unlisted_posts():
    site = "https://www.clearerthinking.org"
    hub = site + "/post/all-clearer-thinking-articles"
    sitemap = {site + "/post/a", site + "/post/a-1", hub}
    redirected = {"/post/a-1"}
    body = "word " * rp.MIN_WORDS
    assert rp.eligible({"url": site + "/post/a", "text": body}, sitemap, redirected, hub)
    assert not rp.eligible({"url": site + "/post/a-1", "text": body}, sitemap, redirected, hub)      # redirects to its original
    assert not rp.eligible({"url": hub, "text": body}, sitemap, redirected, hub)                      # the index page itself
    assert not rp.eligible({"url": site + "/post/noindexed", "text": body}, sitemap, redirected, hub)  # not in the sitemap
    assert not rp.eligible({"url": site + "/post/a", "text": "word " * (rp.MIN_WORDS - 1)}, sitemap, redirected, hub)  # a stub
    assert not rp.eligible({"url": site + "/post/a"}, sitemap, redirected, hub)                       # no body at all


def test_stats_counts_only_posts_that_will_be_set():
    plan = {"k": 3, "posts": [
        {"skip": None, "inbound": 2, "related": [{"similarity": 0.3}, {"similarity": 0.2}, {"similarity": 0.1}]},
        {"skip": None, "inbound": 0, "related": [{"similarity": 0.5}]},
        {"skip": "draft has unpublished changes", "inbound": 2, "related": []}]}
    s = rp.stats(plan)
    assert (s["articles"], s["will_be_set"], s["skipped_pending_edits"], s["links_created"]) == (3, 2, 1, 4)
    assert s["givers_with_fewer_than_3"] == 1 and s["inbound_distribution"] == {0: 1, 2: 2}
    assert s["similarity_min"] == 0.1
