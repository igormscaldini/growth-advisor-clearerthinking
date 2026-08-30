import json
from datetime import date

import data_layer as dl


def test_is_import():
    assert dl._is_import({"utm_channel": "import"}) is True
    assert dl._is_import({"utm_channel": "Import"}) is True
    assert dl._is_import({"utm_channel": "api"}) is False
    assert dl._is_import({}) is False


def test_sub_created_ts():
    assert dl._sub_created_ts({"created": 1788113336}) == 1788113336
    assert dl._sub_created_ts({"created": "2026-08-30T18:08:56Z"}) == 1788113336
    assert dl._sub_created_ts({"created": "nope"}) is None
    assert dl._sub_created_ts({}) is None


def test_rewalk_start():
    assert dl._rewalk_start(None) == dl.NEW_SUBS_FLOOR
    assert dl._rewalk_start({"complete_through": "2026-08-29", "daily": {}}) == date(2026, 8, 28)
    assert dl._rewalk_start({"complete_through": "2025-12-01", "daily": {}}) == dl.NEW_SUBS_FLOOR


def test_merge_new_subs_keeps_old_replaces_recent():
    cache = {"daily": {"2026-08-26": 10, "2026-08-27": 11, "2026-08-28": 12, "2026-08-29": 13}}
    fresh = {"2026-08-28": 20, "2026-08-30": 30}
    merged = dl._merge_new_subs(cache, fresh, date(2026, 8, 28))
    # days before the cutoff come from the cache; the cutoff day onward from the fresh walk
    # (2026-08-29 vanished from fresh, so it must not survive from the cache either)
    assert merged == {"2026-08-26": 10, "2026-08-27": 11, "2026-08-28": 20, "2026-08-30": 30}
    assert dl._merge_new_subs(None, fresh, date(2026, 8, 1)) == fresh


def test_load_cache_rejects_other_floor(tmp_path, monkeypatch):
    f = tmp_path / "cache.json"
    monkeypatch.setattr(dl, "NEW_SUBS_CACHE", f)
    assert dl._load_new_subs_cache() is None
    f.write_text(json.dumps({"floor": "2020-01-01", "complete_through": "2026-08-29", "daily": {}}))
    assert dl._load_new_subs_cache() is None
    f.write_text(json.dumps({"floor": dl.NEW_SUBS_FLOOR.isoformat(), "complete_through": "2026-08-29", "daily": {"2026-08-29": 5}}))
    assert dl._load_new_subs_cache()["daily"] == {"2026-08-29": 5}
    f.write_text("{not json")
    assert dl._load_new_subs_cache() is None
