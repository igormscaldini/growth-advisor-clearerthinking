import hashlib

import pytest

import members_only_programs as mop

TEMPLATE_WITH_LIST = (
    '>> accessKey = "__MEMBERS_ONLY_KEY__"\n'
    "-- BEGIN MEMBER HASHES\n"
    ">> memberHashes = []\n"
    "-- END MEMBER HASHES\n"
    "*if: h in memberHashes\n"
)
TEMPLATE_KEY_ONLY = '>> accessKey = "__MEMBERS_ONLY_KEY__"\n*if: not (k = accessKey)\n'


def test_email_hash_is_md5_of_lowercased_trimmed_email():
    assert mop.email_hash("  Igor@Example.com ") == hashlib.md5(b"igor@example.com").hexdigest()
    assert mop.email_hash("igor@example.com") == mop.email_hash("IGOR@EXAMPLE.COM")


def test_hashes_from_csv_keeps_active_unique_emails(tmp_path):
    p = tmp_path / "subs.csv"
    p.write_text(
        "id,Customer Email,Status\n"
        "s1,a@x.com,active\n"
        "s2,A@X.COM,active\n"  # same person, different case: one hash
        "s3,b@x.com,canceled\n"
        "s4,,active\n"
    )
    assert mop.hashes_from_csv(p) == [mop.email_hash("a@x.com")]


def test_fill_template_replaces_key_and_hash_block():
    out = mop.fill_template(TEMPLATE_WITH_LIST, "abc123", ["h1", "h2"])
    assert '>> accessKey = "abc123"' in out
    assert '>> memberHashes = ["h1", "h2"]' in out
    assert ">> memberHashes = []" not in out
    assert "-- BEGIN MEMBER HASHES\n" in out and "-- END MEMBER HASHES" in out  # markers survive a re-run
    assert "__MEMBERS_ONLY_KEY__" not in out


def test_fill_template_is_idempotent_on_its_own_output():
    once = mop.fill_template(TEMPLATE_WITH_LIST, "k", ["h1"])
    again = mop.HASH_BLOCK.sub(lambda m: f"{m.group(1)}{mop.gt_collection(['h9'])}\n{m.group(2)}", once)
    assert '>> memberHashes = ["h9"]' in again and '"h1"' not in again


def test_fill_template_key_only_template_needs_no_hashes():
    out = mop.fill_template(TEMPLATE_KEY_ONLY, "k", None)
    assert '>> accessKey = "k"' in out


def test_fill_template_rejects_missing_placeholder_or_hashes():
    with pytest.raises(ValueError):
        mop.fill_template("no placeholder here", "k", [])
    with pytest.raises(ValueError):
        mop.fill_template(TEMPLATE_WITH_LIST, "k", None)


def test_real_templates_have_the_placeholders():
    for name in mop.PROGRAMS:
        text = (mop.TEMPLATES / f"{name}.gt").read_text()
        assert mop.KEY_PLACEHOLDER in text, name
    assert mop.HASH_BLOCK.search((mop.TEMPLATES / "Members-Only Content.gt").read_text())
