"""Unit tests for email_transport.send_via_gmail_api (the Gmail client is faked: nothing is sent)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import email_transport  # noqa: E402


class FakeGmail:
    """Records the send / modify calls a googleapiclient Gmail service would receive."""

    def __init__(self, modify_error=None):
        self.calls, self.modify_error = [], modify_error

    def users(self):
        return self

    def messages(self):
        return self

    def send(self, **kwargs):
        self.calls.append(("send", kwargs))
        return self

    def modify(self, **kwargs):
        self.calls.append(("modify", kwargs))
        self._raise = self.modify_error
        return self

    def execute(self):
        err, self._raise = getattr(self, "_raise", None), None
        if err:
            raise err
        return {"id": "msg123"}


def fake_gmail(monkeypatch, **kwargs) -> FakeGmail:
    svc = FakeGmail(**kwargs)
    monkeypatch.setattr("google.oauth2.credentials.Credentials.from_authorized_user_file", lambda path: None)
    monkeypatch.setattr("googleapiclient.discovery.build", lambda *a, **k: svc)
    return svc


def test_default_send_leaves_labels_alone(monkeypatch):
    svc = fake_gmail(monkeypatch)
    email_transport.send_via_gmail_api("s", "b", "to@example.com", "Label", "tag")
    assert [name for name, _ in svc.calls] == ["send"]


def test_to_inbox_labels_the_sent_message_as_unread_inbox_mail(monkeypatch):
    svc = fake_gmail(monkeypatch)
    email_transport.send_via_gmail_api("s", "b", "to@example.com", "Label", "tag", to_inbox=True)
    assert [name for name, _ in svc.calls] == ["send", "modify"]
    assert svc.calls[1][1] == {"userId": "me", "id": "msg123", "body": {"addLabelIds": ["INBOX", "UNREAD"]}}


def test_a_labelling_failure_does_not_fail_the_send(monkeypatch, capsys):
    # Raising here would make send_email fall back to SMTP and deliver the same mail twice.
    svc = fake_gmail(monkeypatch, modify_error=RuntimeError("insufficient scope"))
    email_transport.send_via_gmail_api("s", "b", "to@example.com", "Label", "tag", to_inbox=True)
    assert len(svc.calls) == 2 and "could not move it to the inbox" in capsys.readouterr().err


def test_send_email_passes_to_inbox_through(monkeypatch):
    seen = []
    monkeypatch.setattr(email_transport, "send_via_gmail_api", lambda *a: seen.append(a))
    email_transport.send_email("s", "b", "to@example.com", to_inbox=True)
    email_transport.send_email("s", "b", "to@example.com")
    assert [a[-1] for a in seen] == [True, False]
