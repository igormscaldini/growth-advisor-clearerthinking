"""Mockup-side grouping of RAW GA4 rows (channel, host, landing page, users). The rules themselves live in
the repo-root flow_model.py (shared with data_layer.py and the tests); this module only applies them to
the row shape fetch_data.py pulls."""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from flow_model import CHANNEL_KEY, PAGE_ORDER, SOURCE_ORDER, page_category, source_group  # noqa: E402,F401


def group_landing(rows: list[dict], channel_key: str = CHANNEL_KEY) -> tuple[dict[tuple[str, str], int], int]:
    """(source, page category) -> users, plus the users dropped for not being web sessions."""
    out: dict[tuple[str, str], int] = defaultdict(int)
    dropped = 0
    for r in rows:
        cat = page_category(r.get("hostName"), r.get("landingPage"))
        users = int(r.get("totalUsers") or 0)
        if cat is None:
            dropped += users
            continue
        out[(source_group(r.get(channel_key)), cat)] += users
    return dict(out), dropped


def group_outcomes(rows: list[dict], events: dict[str, str], channel_key: str = CHANNEL_KEY) -> dict[tuple[str, str, str], int]:
    """(source, page category, outcome label) -> users who fired the event in such a session."""
    out: dict[tuple[str, str, str], int] = defaultdict(int)
    for r in rows:
        label = events.get(r.get("eventName") or "")
        cat = page_category(r.get("hostName"), r.get("landingPage"))
        if label is None or cat is None:
            continue
        out[(source_group(r.get(channel_key)), cat, label)] += int(r.get("totalUsers") or 0)
    return dict(out)
