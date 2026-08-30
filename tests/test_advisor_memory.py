from datetime import date, timedelta

import pytest

import advisor_memory as am


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setenv(am.KEY_ENV, am.generate_key())
    monkeypatch.setattr(am, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(am, "CONVERSATIONS_DIR", tmp_path / "conversations")
    monkeypatch.setattr(am, "DURABLE_FILE", tmp_path / "durable.md.enc")
    return tmp_path


def test_round_trip(store):
    blob = am.encrypt_text("hello, wörld")
    assert blob != "hello, wörld".encode()
    assert am.decrypt_text(blob) == "hello, wörld"


def test_missing_key_is_explicit(monkeypatch):
    monkeypatch.delenv(am.KEY_ENV, raising=False)
    with pytest.raises(am.MemoryKeyMissing):
        am.encrypt_text("x")


def test_wrong_key_fails(store, monkeypatch):
    blob = am.encrypt_text("secret")
    monkeypatch.setenv(am.KEY_ENV, am.generate_key())
    with pytest.raises(Exception):
        am.decrypt_text(blob)


def test_digest_path_and_replace(store):
    sid = "58351d99-670f-4e0b-92a0-c80e1a81eb0d"
    old = am.digest_path(sid, date(2026, 8, 26))
    new = am.digest_path(sid, date(2026, 8, 30))
    assert old.name == "2026-08-26_58351d99.md.enc"
    am.write_encrypted(old, "v1")
    am.write_encrypted(new, "v2")
    removed = am.remove_other_digests(sid, keep=new)
    assert removed == [old] and not old.exists() and new.exists()


def test_recent_conversations_window_order_and_cap(store):
    ref = date(2026, 8, 30)
    am.write_encrypted(am.digest_path("aaaaaaaa", ref - timedelta(days=8)), "too old")
    am.write_encrypted(am.digest_path("bbbbbbbb", ref - timedelta(days=6)), "six days ago")
    am.write_encrypted(am.digest_path("cccccccc", ref), "today")
    am.write_encrypted(am.digest_path("dddddddd", ref + timedelta(days=1)), "future")
    text = am.load_recent_conversations(days=7, ref=ref)
    assert "too old" not in text and "future" not in text
    assert text.index("six days ago") < text.index("today")
    assert "Session on 2026-08-24 (id bbbbbbbb)" in text
    # Cap drops the OLDEST first and says so.
    capped = am.load_recent_conversations(days=7, ref=ref, max_chars=80)
    assert "today" in capped and "six days ago" not in capped and "omitted" in capped
    assert am.load_recent_conversations(days=1, ref=ref - timedelta(days=30)) == ""


def test_durable_memory_append_and_load(store):
    assert am.load_durable_memory() == ""
    assert am.append_durable_memory("   ") == ""
    line = am.append_durable_memory("Igor cares more about MRR than gross revenue.", "preference", when=date(2026, 8, 30))
    assert line == "\n## 2026-08-30 (preference)\nIgor cares more about MRR than gross revenue.\n"
    am.append_durable_memory("Second fact.", when=date(2026, 8, 31))
    text = am.load_durable_memory()
    assert text.startswith("# Advisor durable memory")
    assert "MRR" in text and "Second fact." in text
    assert am.load_durable_memory(max_chars=15) == text[-15:] and text.endswith("Second fact.\n")


def test_list_digests_ignores_foreign_files(store):
    am.write_encrypted(am.digest_path("abcdef12", date(2026, 8, 1)), "x")
    (am.CONVERSATIONS_DIR / "notes.txt").write_text("nope")
    rows = am.list_conversation_digests()
    assert [r["session"] for r in rows] == ["abcdef12"]
