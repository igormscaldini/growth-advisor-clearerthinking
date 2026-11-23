"""GA4 users per 2026 article (main post + its study report in ONE query, so people are not counted twice),
Jan 1 to END. Two numbers per article: users from every source except our own emails and the (not set) scanner
sessions ("web_users", the one that enters the ranking), and users from our own emails ("own_email_users",
shown only, since email readers are already counted through unique opens). Writes data/ga4_articles.json."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
import ga4_client as g  # noqa: E402
from google.analytics.data_v1beta.types import (DateRange, Dimension, Filter, FilterExpression,  # noqa: E402
                                                FilterExpressionList, Metric, RunReportRequest)

from rules import END, OWN_EMAIL_SOURCES, START  # noqa: E402

S = Filter.StringFilter


def _in(field, values):
    return FilterExpression(filter=Filter(field_name=field, in_list_filter=Filter.InListFilter(values=list(values))))


def users(client, paths, own_email: bool) -> int:
    src = _in("sessionSource", OWN_EMAIL_SOURCES)
    exprs = [_in("pagePath", paths),
             FilterExpression(filter=Filter(field_name="hostName", string_filter=S(value="www.clearerthinking.org")))]
    exprs.append(src if own_email else FilterExpression(not_expression=_in("sessionSource", OWN_EMAIL_SOURCES + ["(not set)"])))
    r = client.run_report(RunReportRequest(property=g.property_path(), date_ranges=[DateRange(start_date=START, end_date=END)],
                                           metrics=[Metric(name="totalUsers")],
                                           dimension_filter=FilterExpression(and_group=FilterExpressionList(expressions=exprs))))
    return int(r.rows[0].metric_values[0].value) if r.rows else 0


if __name__ == "__main__":
    client = g.get_client()
    out = {}
    for a in json.loads((HERE / "articles.json").read_text())["articles"]:
        paths = ["/post/" + s for s in [a["slug"]] + a.get("extra_slugs", [])] + a.get("extra_paths", [])
        out[a["slug"]] = {"paths": paths, "web_users": users(client, paths, False), "own_email_users": users(client, paths, True)}
        print(a["slug"][:50], out[a["slug"]]["web_users"], out[a["slug"]]["own_email_users"])
    (HERE / "data" / "ga4_articles.json").write_text(json.dumps({"start": START, "end": END, "articles": out}, indent=1))


# Tools the Nov 19 tools ranking leaves out (Igor's exclusions there) or cannot see, counted here so the year-end
# list can say where they land. Prefix match on programs.* (every page of the tool); external hosts by hostName.
TOOL_EXTRAS = {"Who Attracts You?": ("programs.clearerthinking.org", "/who_attracts_you"),
               "Cognitive Assessment": ("programs.clearerthinking.org", "/cognitive-test"),
               "Self-Help Evidence Pyramid": ("selfhelppyramid.clearerthinking.org", None),
               "Society Explained": ("society.clearerthinking.org", None),
               "Demystifying Meditation": ("meditation.clearerthinking.org", None)}


def tool_extras(client) -> dict:
    out = {}
    for name, (host, prefix) in TOOL_EXTRAS.items():
        ex = [FilterExpression(filter=Filter(field_name="hostName", string_filter=S(value=host)))]
        if prefix:
            ex.append(FilterExpression(filter=Filter(field_name="pagePath", string_filter=S(match_type=S.MatchType.BEGINS_WITH, value=prefix))))
        r = client.run_report(RunReportRequest(property=g.property_path(), date_ranges=[DateRange(start_date=START, end_date=END)],
                                               metrics=[Metric(name="totalUsers")],
                                               dimension_filter=FilterExpression(and_group=FilterExpressionList(expressions=ex))))
        out[name] = int(r.rows[0].metric_values[0].value) if r.rows else 0
    return out


if __name__ == "__main__":
    extras = tool_extras(g.get_client())
    (HERE / "data" / "ga4_tool_extras.json").write_text(json.dumps({"start": START, "end": END, "users": extras}, indent=1))
    print(extras)
