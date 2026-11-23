"""Every rule of the 2026 top-content ranking, in one place."""
START, END = "2026-01-01", "2026-11-22"  # GA4 window: the year so far (last complete day before the analysis)
# Session sources that are Clearer Thinking's own emails (their readers are counted through unique opens instead).
OWN_EMAIL_SOURCES = ["clearerthinking.beehiiv.com", "ClearerThinking.org", "app.beehiiv.com", "behiiv", "drip_campaign"]
MIN_SEND_RECIPIENTS = 100  # beehiiv posts below this are test sends


def article_reach(unique_opens: list[int], web_users: int) -> int:
    """People reached by one article = unique opens summed over its sends + GA4 users from non-email sources."""
    return sum(unique_opens) + web_users


def rank(rows: list[dict], key: str = "reach", n: int = 10) -> list[dict]:
    """Top `n` rows by `key`, ties broken by title so the order is stable."""
    return sorted(rows, key=lambda r: (-r[key], r.get("title", "")))[:n]
