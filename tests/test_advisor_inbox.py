import base64

import advisor_inbox as ai


def test_is_bulk_rules():
    assert ai.is_bulk({"list-unsubscribe": "<mailto:x>"}) is True
    assert ai.is_bulk({"list-id": "news.example.com"}) is True
    assert ai.is_bulk({"precedence": "Bulk"}) is True
    assert ai.is_bulk({"auto-submitted": "auto-generated"}) is True
    assert ai.is_bulk({"auto-submitted": "no", "from": "Tee Barnett <tee@example.com>"}) is False
    assert ai.is_bulk({"from": "GitHub <noreply@github.com>"}) is True
    assert ai.is_bulk({"from": "Stripe <notifications@stripe.com>"}) is True
    assert ai.is_bulk({"from": "Spencer <spencer@example.org>"}) is False


def test_direction():
    assert ai.direction({"from": f"Igor <{ai.OWN_ADDRESS}>"}, []) == "sent"
    assert ai.direction({"from": "someone@example.com"}, ["SENT"]) == "sent"
    assert ai.direction({"from": "someone@example.com"}, ["INBOX"]) == "received"


def _m(i, ts, direction="received", bulk=False, advisor=False, thread=None, **kw):
    d = {"id": str(i), "thread": thread or f"t{i}", "ts": ts, "from": f"p{i}@x.com", "to": "igor",
         "subject": f"S{i}", "snippet": f"snip {i}", "bulk": bulk, "advisor": advisor, "direction": direction}
    d.update(kw)
    return d


def test_select_messages_prefers_sent_then_newest_and_caps():
    metas = [
        _m(1, 100), _m(2, 300, bulk=True), _m(3, 200, direction="sent"), _m(4, 400, advisor=True),
        _m(5, 500), _m(6, 50, direction="sent"),
    ]
    out = ai.select_messages(metas, max_messages=3)
    assert [m["id"] for m in out] == ["3", "6", "5"]   # sent (newest first), then newest received
    assert [m["id"] for m in ai.select_messages(metas, 10)] == ["3", "6", "5", "1"]


def test_render_threads_groups_and_orders():
    msgs = [
        _m(1, 1_000_000, thread="A", subject="Workshop", body="Can you send the list?"),
        _m(2, 1_100_000, thread="A", direction="sent", to="tee@x.com", body="Sure, attached."),
        _m(3, 2_000_000, thread="B", subject="Podcast idea", snippet="Let's record next week"),
    ]
    text = ai.render_threads(msgs)
    assert text.startswith("### Podcast idea (1 message)")          # newest thread first
    assert "### Workshop (2 messages)" in text
    assert text.index("Can you send the list?") < text.index("Sure, attached.")  # chronological inside a thread
    assert "Igor -> tee@x.com" in text and "p1@x.com -> Igor" in text
    assert "Let's record next week" in text                          # snippet fallback when no body


def test_extract_plain_strips_quoted_reply():
    body = "Thanks, sounds good.\n\nOn Mon, Aug 24, 2026, Tee wrote:\n> old stuff\n> more"
    payload = {"mimeType": "multipart/alternative", "parts": [
        {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(b"<p>x</p>").decode()}},
        {"mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()}},
    ]}
    assert ai.extract_plain(payload) == "Thanks, sounds good."
    assert ai.extract_plain({}) == ""
