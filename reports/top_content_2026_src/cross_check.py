"""Independent recount of the article ranking, without articles.json's hand-made send map.
Email: every beehiiv send of 100+ recipients grouped by exact subject line; the top-10 articles' totals are compared
with the best-matching subject groups. Last run 2026-11-23: all ten match exactly. (Web users are not re-checked:
outside the AI study they are under 2% of each article's total.)"""
import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
posts = [p for p in json.loads((HERE / "data/beehiiv_posts.json").read_text()) if (p["recipients"] or 0) >= 100]
by_subject = defaultdict(int)
for p in posts:
    by_subject[re.sub(r"\s+", " ", (p["subject_line"] or "").strip().lower())] += int(p["unique_opens"] or 0)
dp = json.loads((HERE / "datapoints.json").read_text())


def words(s):
    return set(re.findall(r"[a-z]{4,}", s.lower()))


for a in dp["top10"]:
    best = max(by_subject, key=lambda s: len(words(s) & words(a["title"])) / (len(words(s)) or 1))
    # the A/B test of "biases" used two subjects; all others use one subject per article
    print(f"{a['unique_opens']:>8,} vs {by_subject[best]:>8,}  {'OK ' if a['unique_opens'] == by_subject[best] else 'DIFF'}  {a['title'][:45]}  <- '{best[:45]}'")
