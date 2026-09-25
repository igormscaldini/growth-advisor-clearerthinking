"""Send-strategy analysis of Clearer Thinking's beehiiv newsletter.

Pure functions (post classification, audience labels, rate metrics, drift-normalised
click index, subject-line features, GA4 timing curves) plus `main()`, which turns the
cached pulls in data/ into datapoints.json for build_report.py.

Tests: tests/test_newsletter_send_strategy.py. Data refresh: fetch_data.py.
"""
from __future__ import annotations

import json
import math
import random
import re
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
ET = ZoneInfo("America/New_York")
OHI_DOMAIN = "ohi.clearerthinking.net"

# bare segment uuid -> (label, class). Classes: engaged / all / none / high / plus / half / rest.
SEGMENT_LABELS = {
    "ead5b83a-5655-44cf-82a4-e5d63f1b9c49": ("CT engaged", "engaged"),
    "3a41736c-0983-4690-afab-f12c09f15225": ("CT engaged (older definition, segment since deleted)", "engaged"),
    "316da142-9363-4e75-a895-c5237089fe7f": ("OHI engaged", "engaged"),
    "0f05394c-35e7-4a04-b790-a12f9a23231c": ("CT audience, all", "all"),
    "d8773b67-e549-4165-9d72-dc93d5db8922": ("OHI audience, all", "all"),
    "d884becb-4a59-4140-9d74-8082ad9f6a3d": ("OHI audience legacy, all", "all"),
    "8c190f72-7019-4cd9-8ea4-339b147a3208": ("0% openers", "none"),
    "188740a6-d50b-4154-bfd1-a5ff319a6095": ("disengaged (drip)", "none"),
    "6a37f9ee-95d0-4bee-b23c-f93e2e9a4dca": ("open rate > 40%", "high"),
    "0b1106c5-0e03-43e5-a2f0-17d50634e898": ("100% openers", "high"),
    "233ffb48-5cec-457b-96f6-28e28aa5a3bc": ("50-99% openers", "high"),
    "d135305a-7bee-49f3-80af-1dfeb31f5d48": ("very engaged", "high"),
    "f53a6bf0-8c25-4096-8880-672ce460396e": ("open rate > 95%", "high"),
    "c15a0c8f-386b-4f15-9118-0a21a4451ee9": ("meditation-launch half (static)", "half"),
    "e3452176-b296-4227-a332-1efc66251054": ("second send, society tool", "rest"),
    "6ea82e6e-7659-44b1-b40b-94c29f656309": ("CT+ active supporters", "plus"),
    "fb5646a8-07a7-4a6f-bc1a-e019c3f6c4af": ("CT+ members", "plus"),
    "0cbc4c21-e888-4997-94b3-5a4add12e43a": ("beta testers", "other"),
}

EVENT_RE = re.compile(
    r"workshop|webinar|reminder|about to start|recording|forked by ai|see you tomorrow|"
    r"productivity equation|self-help technique|coaching session", re.I)
RECRUIT_RE = re.compile(r"beta tester|participate in a study|thank-you|thank you for|early access", re.I)
PROMO_RE = re.compile(
    r"reconstellation|bluedot|wiser swap|introducing clearer thinking plus|welcome to clearer thinking plus|"
    r"12 levers book launch|12 levers is out|link fixed|dating app|missed our invitation|personal ask before launch",
    re.I)
TRANSACTIONAL_RE = re.compile(r"personality report", re.I)
TOOL_RE = re.compile(r"\btools?\b|self-help pyramid|who attracts you|moral compass|unusual traits|demystifying meditation", re.I)
RESEND_SUFFIX_RE = re.compile(r"\s*(\(1\)|\(2\)|- ohi-domain|- ct-domain|- 50 - 100% OR|- Everyone else|- Re-launch)\s*$", re.I)


# ----------------------------------------------------------------------------- classification
def base_title(title: str) -> str:
    """Strip the suffixes beehiiv duplicates and Igor's manual variants add to a title."""
    return RESEND_SUFFIX_RE.sub("", title or "").strip()


def classify(post: dict) -> str:
    """Category of a send: test / ohi / coaching_outreach / event / recruitment / promo /
    transactional / wrapup / small / core. `core` is the Clearer Thinking newsletter proper
    (articles, data studies, tool launches)."""
    title = post.get("title") or ""
    rec = post.get("recipients") or 0
    if rec < 50:
        return "test"
    if title.lower().startswith("one helpful idea"):
        return "ohi"
    if "coaching-outreach" in (post.get("content_tags") or []) or "coaching session" in title.lower():
        return "coaching_outreach"
    if EVENT_RE.search(title):
        return "event"
    if RECRUIT_RE.search(title):
        return "recruitment"
    if PROMO_RE.search(title):
        return "promo"
    if TRANSACTIONAL_RE.search(title):
        return "transactional"
    if "monthly debrief" in title.lower():
        return "wrapup"
    if rec < 1000:
        return "small"
    return "core"


def core_subtype(post: dict) -> str:
    text = f"{post.get('title', '')} {post.get('subject_line', '')}"
    return "tool_launch" if TOOL_RE.search(text) else "article"


def audience_class(send_targets: list[dict]) -> tuple[str, str]:
    """(class, label) of the audience a send went to, from beehiiv's send_targets.

    Classes: all (whole list), all_minus_nonopeners, engaged, engaged_minus_high, rest
    (whole list minus the engaged segment), high (top openers), plus, other."""
    inc = [t for t in (send_targets or []) if t.get("action") == "include"]
    exc = [t for t in (send_targets or []) if t.get("action") == "exclude"]
    inc_pub = any(t.get("receiver_type") == "Publication" for t in inc)
    inc_cls = {SEGMENT_LABELS.get(t.get("receiver_id"), ("?", "other"))[1] for t in inc if t.get("receiver_type") == "Segment"}
    exc_cls = {SEGMENT_LABELS.get(t.get("receiver_id"), ("?", "other"))[1] for t in exc}
    if inc_pub:
        if "engaged" in exc_cls:
            return "rest", "Whole list minus engaged"
        if exc_cls & {"none"}:
            return "all", "Whole list minus disengaged"
        return "all", "Whole list"
    if "engaged" in inc_cls:
        if "high" in exc_cls:
            return "engaged_minus_high", "Engaged minus top openers"
        return "engaged", "Engaged segment"
    if "all" in inc_cls:
        if "none" in exc_cls:
            return "all_minus_nonopeners", "CT audience minus 0% openers"
        return "all", "CT audience, all"
    if "high" in inc_cls:
        return "high", "Top openers"
    if "plus" in inc_cls:
        return "plus", "CT+ members"
    return "other", "Other segment"


# ----------------------------------------------------------------------------- metrics
def rates(email_stats: dict) -> dict:
    """Open / click / unsubscribe / spam rates per delivered email. Clicks use beehiiv's
    verified unique clicks (bot-filtered) when present, else unique clicks."""
    d = email_stats.get("delivered") or email_stats.get("recipients") or 0
    uo = email_stats.get("unique_opens") or 0
    uc = email_stats.get("unique_clicks") or 0
    uvc = email_stats.get("unique_verified_clicks")
    clicks = uvc if uvc is not None else uc
    return {
        "delivered": d,
        "unique_opens": uo,
        "unique_clicks": uc,
        "verified_clicks": clicks,
        "open_rate": uo / d if d else 0.0,
        "click_rate": clicks / d if d else 0.0,
        "raw_click_rate": uc / d if d else 0.0,
        "ctor": clicks / uo if uo else 0.0,
        "unsub_rate": (email_stats.get("unsubscribes") or 0) / d if d else 0.0,
        "spam_rate": (email_stats.get("spam_reports") or 0) / d if d else 0.0,
    }


def neighbour_index(values: list[float], k: int = 3) -> list[float]:
    """Each value divided by the median of its up-to-k neighbours on each side (self excluded).
    Removes slow drift (list quality, deliverability) so sends months apart can be compared.
    Returns 1.0 where no neighbours or the neighbour median is 0."""
    out = []
    n = len(values)
    for i, v in enumerate(values):
        nb = [values[j] for j in range(max(0, i - k), min(n, i + k + 1)) if j != i]
        med = statistics.median(nb) if nb else 0.0
        out.append(v / med if med > 0 else 1.0)
    return out


# ----------------------------------------------------------------------------- subject lines
QUESTION_WORD_RE = re.compile(r"^(how|why|what|when|where|which|who|can|should|do|does|is|are|have)\b", re.I)
PERSONAL_RE = re.compile(r"\b(you|your|you're|yourself)\b", re.I)
EVIDENCE_RE = re.compile(r"\b(data|science|scientific|study|studies|research|evidence|experts?)\b", re.I)
PSYCH_RE = re.compile(r"personality|narciss|sociopath|psycholog|\bIQ\b|trauma|depression|anxiety|disorder|cult|attracts", re.I)
NEGATIVE_RE = re.compile(r"\b(stop|don't|fooled|myths?|dangerous|lies|wrong|scams?|fail|failing|doubt|fabricated)\b", re.I)


def subject_features(subject: str, title: str = "", preview: str = "", subtitle: str = "") -> dict:
    s = subject or ""
    words = s.split()
    return {
        "question": "?" in s,
        "question_word": bool(QUESTION_WORD_RE.search(s)),
        "personal": bool(PERSONAL_RE.search(s)),
        "number": bool(re.search(r"\d", s)),
        "bracket_tag": bool(re.search(r"\[[^\]]+\]", s)),
        "parenthetical": "(" in s,
        "tool": bool(re.search(r"\btools?\b", s, re.I)),
        "evidence": bool(EVIDENCE_RE.search(s)),
        "psych_topic": bool(PSYCH_RE.search(s)),
        "negative": bool(NEGATIVE_RE.search(s)),
        "short": len(words) <= 7,
        "rewritten": s.strip().lower() != (title or "").strip().lower(),
        "custom_preview": bool(preview) and (preview or "").strip() != (subtitle or "").strip(),
        "words": len(words),
        "chars": len(s),
    }


def mean_log_ratio(a: list[float], b: list[float]) -> float:
    """log2 of geometric-mean ratio between groups (a over b); 0 if either is empty."""
    if not a or not b:
        return 0.0
    la = statistics.mean(math.log2(max(x, 1e-9)) for x in a)
    lb = statistics.mean(math.log2(max(x, 1e-9)) for x in b)
    return la - lb


def permutation_p(a: list[float], b: list[float], n_perm: int = 5000, seed: int = 0) -> float:
    """Two-sided permutation p-value for the mean_log_ratio difference between groups."""
    if len(a) < 2 or len(b) < 2:
        return 1.0
    obs = abs(mean_log_ratio(a, b))
    pool = list(a) + list(b)
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(pool)
        if abs(mean_log_ratio(pool[: len(a)], pool[len(a):])) >= obs - 1e-12:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def feature_effects(rows: list[dict], metric: str, features: list[str]) -> list[dict]:
    """For each binary feature: n with/without, geometric-mean ratio of `metric` (with over
    without), and a permutation p-value."""
    out = []
    for f in features:
        a = [r[metric] for r in rows if r["features"][f]]
        b = [r[metric] for r in rows if not r["features"][f]]
        lr = mean_log_ratio(a, b)
        out.append({"feature": f, "n_with": len(a), "n_without": len(b), "ratio": 2 ** lr,
                    "p": permutation_p(a, b)})
    return out


# ----------------------------------------------------------------------------- timing (GA4)
def rel_hour_hist(send_utc: datetime, hour_counts: dict[str, int]) -> dict[int, int]:
    """Histogram of clicks by whole hours since send. hour_counts keys are GA4 dateHour
    strings (YYYYMMDDHH) in the property's timezone (US Eastern)."""
    out: dict[int, int] = defaultdict(int)
    for dh, n in hour_counts.items():
        t = datetime.strptime(dh, "%Y%m%d%H").replace(tzinfo=ET).astimezone(timezone.utc)
        out[int((t - send_utc).total_seconds() // 3600)] += int(n)
    return dict(out)


def tail_hour_hist(send_utc: datetime, hour_counts: dict[str, int], min_hours: int = 24) -> tuple[list[int], list[int]]:
    """(hour-of-day ET histogram, weekday histogram Mon=0) of clicks at least `min_hours`
    after the send: reading habits with the send moment itself removed."""
    hours = [0] * 24
    wdays = [0] * 7
    for dh, n in hour_counts.items():
        t_et = datetime.strptime(dh, "%Y%m%d%H").replace(tzinfo=ET)
        if (t_et.astimezone(timezone.utc) - send_utc).total_seconds() >= min_hours * 3600:
            hours[t_et.hour] += int(n)
            wdays[t_et.weekday()] += int(n)
    return hours, wdays


BUCKETS = [(-48, 0, "before send"), (0, 1, "0-1 h"), (1, 3, "1-3 h"), (3, 6, "3-6 h"), (6, 12, "6-12 h"),
           (12, 24, "12-24 h"), (24, 48, "day 2"), (48, 96, "days 3-4"), (96, 168, "days 5-7"), (168, 10 ** 6, "after a week")]


def bucket_shares(rel_hours: dict, total: int) -> list[float]:
    return [sum(n for h, n in rel_hours.items() if lo <= int(h) < hi) / total if total else 0.0 for lo, hi, _ in BUCKETS]


# ----------------------------------------------------------------------------- main
def load_posts() -> list[dict]:
    posts = json.load(open(DATA / "posts.json"))
    for p in posts:
        p["dt"] = datetime.fromtimestamp(p["publish_date"], tz=timezone.utc)
        p["dt_et"] = p["dt"].astimezone(ET)
        p["recipients"] = (p.get("email") or {}).get("recipients") or 0
        p["category"] = classify(p)
        p["subtype"] = core_subtype(p) if p["category"] == "core" else ""
        p["base_title"] = base_title(p["title"])
        p["aud_class"], p["aud_label"] = audience_class(p.get("send_targets"))
        p["domain"] = "OHI" if OHI_DOMAIN in (p.get("from_address") or "") else "CT"
        p.update(rates(p.get("email") or {}))
    posts.sort(key=lambda p: p["publish_date"])
    # resends: a later core send whose base title matches an earlier core send
    seen: dict[str, int] = {}
    for p in posts:
        if p["category"] != "core":
            p["resend"] = False
            continue
        p["resend"] = p["base_title"] in seen and p["title"] != p["base_title"] and p["aud_class"] != "engaged"
        if p["base_title"] not in seen:
            seen[p["base_title"]] = p["publish_date"]
    # the two halves of the domain test are both primary sends of one campaign
    for p in posts:
        if p["title"].endswith("ct-domain"):
            p["resend"] = False
            p["domain_test"] = True
        elif p["title"].endswith("ohi-domain"):
            p["domain_test"] = True
        else:
            p["domain_test"] = False
    return posts


def primary_core(posts: list[dict]) -> list[dict]:
    return [p for p in posts if p["category"] == "core" and not p["resend"] and not p["title"].endswith("ct-domain")]


def pair_groups(posts: list[dict]) -> list[list[dict]]:
    """Groups of >= 2 sizeable sends of the same campaign to different audiences."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for p in posts:
        if p["category"] == "core" and p["recipients"] >= 10_000:
            groups[p["base_title"]].append(p)
    return [g for g in groups.values() if len(g) >= 2]


def slim(p: dict) -> dict:
    keep = ["id", "title", "subject_line", "preview_text", "subtitle", "category", "subtype", "resend", "domain_test",
            "aud_class", "aud_label", "domain", "split_tested", "recipients", "delivered", "unique_opens",
            "verified_clicks", "unique_clicks", "open_rate", "click_rate", "raw_click_rate", "ctor", "unsub_rate",
            "spam_rate", "slug"]
    d = {k: p.get(k) for k in keep}
    d["date_utc"] = p["dt"].strftime("%Y-%m-%d %H:%M")
    d["date_et"] = p["dt_et"].strftime("%a %Y-%m-%d %I:%M %p")
    d["weekday_et"] = p["dt_et"].strftime("%a")
    d["hour_et"] = p["dt_et"].hour
    return d


def main() -> dict:
    posts = load_posts()
    core = primary_core(posts)
    ga4 = json.load(open(DATA / "ga4_timing.json"))
    by_slug = {p["slug"]: p for p in posts}

    # --- subject lines: index each primary core send against its neighbours in the same audience class
    for cls in {p["aud_class"] for p in core}:
        grp = [p for p in core if p["aud_class"] == cls]
        ci = neighbour_index([p["click_rate"] for p in grp])
        oi = neighbour_index([p["open_rate"] for p in grp])
        for p, c, o in zip(grp, ci, oi):
            p["click_index"], p["open_index"] = c, o
    for p in core:
        p["features"] = subject_features(p["subject_line"], p["title"], p.get("preview_text"), p.get("subtitle"))
    big_core = [p for p in core if p["recipients"] >= 100_000]
    feats = ["question", "question_word", "personal", "number", "bracket_tag", "parenthetical", "tool", "evidence",
             "psych_topic", "negative", "short", "rewritten", "custom_preview"]
    effects_click = feature_effects(big_core, "click_index", feats)
    effects_open = feature_effects(big_core, "open_index", feats)

    # --- timing from GA4
    timing_rows = []
    for slug, t in ga4.items():
        p = by_slug.get(slug)
        if not p or p["category"] not in ("core", "wrapup") or p["recipients"] < 100_000 or t["total"] < 100:
            continue
        timing_rows.append({"slug": slug, "title": p["title"], "date_et": p["dt_et"].strftime("%a %Y-%m-%d %I:%M %p"),
                            "hour_et": p["dt_et"].hour, "weekday_et": p["dt_et"].strftime("%a"), "total": t["total"],
                            "shares": bucket_shares(t["rel_hours"], t["total"]), "tail_hours": t["tail_hours"],
                            "tail_wdays": t["tail_wdays"], "resend": p["resend"], "aud_class": p["aud_class"]})
    n_b = len(BUCKETS)
    median_shares = [statistics.median(r["shares"][i] for r in timing_rows) if timing_rows else 0 for i in range(n_b)]
    tail_hours = [sum(r["tail_hours"][h] for r in timing_rows) for h in range(24)]
    tail_wdays = [sum(r["tail_wdays"][d] for r in timing_rows) for d in range(7)]

    out = {
        "generated_at": datetime.now(ET).strftime("%Y-%m-%d %I:%M%p").lower(),
        "n_posts": len(posts),
        "category_counts": {c: sum(1 for p in posts if p["category"] == c) for c in sorted({p["category"] for p in posts})},
        "posts": [slim(p) for p in posts],
        "core": [dict(slim(p), click_index=p["click_index"], open_index=p["open_index"], features=p["features"]) for p in core],
        "pairs": [[slim(p) for p in g] for g in pair_groups(posts)],
        "subject_effects": {"click": effects_click, "open": effects_open, "n": len(big_core)},
        "timing": {"rows": timing_rows, "bucket_labels": [b[2] for b in BUCKETS], "median_shares": median_shares,
                   "tail_hours_et": tail_hours, "tail_wdays": tail_wdays},
        "country": json.load(open(DATA / "ga4_country.json")),
        "isp": json.load(open(DATA / "isp_domain_test.json")) if (DATA / "isp_domain_test.json").exists() else None,
    }
    json.dump(out, open(HERE / "datapoints.json", "w"), indent=1, default=str)
    return out


if __name__ == "__main__":
    d = main()
    print("posts", d["n_posts"], d["category_counts"])
    print("primary core sends:", len(d["core"]))
    for e in sorted(d["subject_effects"]["click"], key=lambda e: e["p"]):
        print(f"  click  {e['feature']:<15} with={e['n_with']:>2} without={e['n_without']:>2} ratio={e['ratio']:.2f} p={e['p']:.3f}")
    for e in sorted(d["subject_effects"]["open"], key=lambda e: e["p"]):
        print(f"  open   {e['feature']:<15} with={e['n_with']:>2} without={e['n_without']:>2} ratio={e['ratio']:.2f} p={e['p']:.3f}")
    print("timing campaigns:", len(d["timing"]["rows"]))
    for lab, s in zip(d["timing"]["bucket_labels"], d["timing"]["median_shares"]):
        print(f"  {lab:<13} {s*100:5.1f}%")
