"""2026 articles ranked by people reached: beehiiv unique opens (every send of the article) + GA4 users from
non-email sources. Reads articles.json + data/, writes datapoints.json."""
import json
from datetime import datetime, timezone
from pathlib import Path

from rules import MIN_SEND_RECIPIENTS, article_reach, rank

HERE = Path(__file__).parent


def build():
    cfg = json.loads((HERE / "articles.json").read_text())
    posts = {p["id"][5:13]: p for p in json.loads((HERE / "data" / "beehiiv_posts.json").read_text())}
    wix = {p["slug"]: p for p in json.loads((HERE / "data" / "wix_posts.json").read_text())}
    ga4 = json.loads((HERE / "data" / "ga4_articles.json").read_text())
    rows = []
    for a in cfg["articles"]:
        sends = [posts[i] for i in a["sends"] if (posts[i]["recipients"] or 0) >= MIN_SEND_RECIPIENTS]
        opens = [int(s["unique_opens"] or 0) for s in sends]
        g = ga4["articles"][a["slug"]]
        first_send = min(s["publish_date"] for s in sends)
        rows.append({
            "title": wix[a["slug"]]["title"], "url": wix[a["slug"]]["url"],
            "published": wix[a["slug"]]["first_published"][:10],
            "emailed": datetime.fromtimestamp(first_send, tz=timezone.utc).strftime("%Y-%m-%d"),
            "sends": len(sends), "recipients": sum(int(s["recipients"] or 0) for s in sends),
            "unique_opens": sum(opens), "web_users": g["web_users"], "own_email_web_users": g["own_email_users"],
            "reach": article_reach(opens, g["web_users"]), "note": a.get("note", ""),
        })
    not_blog = [{"subject": posts[i]["subject_line"], "label": lbl, "recipients": posts[i]["recipients"],
                 "unique_opens": posts[i]["unique_opens"]}
                for i, lbl in cfg["not_blog_articles"]["sends"].items()]
    return {"window": {"start": ga4["start"], "end": ga4["end"]}, "articles": rank(rows, n=len(rows)),
            "top10": rank(rows), "not_blog_sends": not_blog, "tools": tools()}


def tools():
    """Tools by 2026 GA4 users on their own pages (the Nov 19 tools ranking's rules: partner copies left out),
    plus Who Attracts You?, which that ranking excluded but which is this year's most used tool by far."""
    t = json.loads((HERE / "data" / "tools_ga4.json").read_text())
    ytd = t["windows"]["ytd"]
    rows = [{"title": t["tools"][b]["name"], "url": t["tools"][b]["url"], "launched": t["tools"][b].get("launch_date") or "",
             "users": v["own"]["users"]} for b, v in ytd["tools"].items() if "users" in v["own"]]
    extras = json.loads((HERE / "data" / "ga4_tool_extras.json").read_text())["users"]
    rows.append({"title": "Who Attracts You?", "url": "https://programs.clearerthinking.org/who_attracts_you_study.html",
                 "launched": "2026-08", "users": extras["Who Attracts You?"],
                 "note": "left out of the Nov 19 tools ranking at Igor's request; included here"})
    with_partner = {t["tools"][b]["name"]: v["with_partner"]["users"] for b, v in ytd["tools"].items()
                    if "users" in v["with_partner"] and v["with_partner"]["users"] > v["own"].get("users", 0) * 1.5}
    return {"window": {"start": ytd["start"], "end": ytd["end"]}, "top10": rank(rows, key="users"),
            "not_ranked": {"Cognitive Assessment (paid; excluded in the Nov 19 ranking)": extras["Cognitive Assessment"],
                           **{k + " (own subdomain, not tracked in this GA4 property)": None
                              for k in ("Self-Help Evidence Pyramid", "Society Explained", "Demystifying Meditation")},
                           "Guess Which Experiments Replicate (hosted on 80000hours.org)": None},
            "partner_copies_much_larger": with_partner}


if __name__ == "__main__":
    d = build()
    (HERE / "datapoints.json").write_text(json.dumps(d, indent=1, ensure_ascii=False))
    for i, r in enumerate(d["articles"], 1):
        print(f"{i:2} {r['reach']:>7,} = {r['unique_opens']:>7,} + {r['web_users']:>6,} | rcpt {r['recipients']:>7,} | {r['emailed']} | {r['title'][:60]}")
    for i, r in enumerate(d["tools"]["top10"], 1):
        print(f"T{i:2} {r['users']:>9,} | {r['launched']} | {r['title']}")
    print(d["tools"]["not_ranked"], d["tools"]["partner_copies_much_larger"])
    print("not blog:", [(x["label"][:40], x["unique_opens"]) for x in d["not_blog_sends"]])
