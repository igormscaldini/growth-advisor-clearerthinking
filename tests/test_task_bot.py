"""Task bot: reading Igor's email, deciding who it is from, the guardrails, the outcome and the log.

Nothing here touches Gmail, Stripe, beehiiv or Sheets: those calls are replaced by fakes, and the
context file lives in pytest's tmp_path.
"""
import base64
import json
from datetime import datetime, timedelta, timezone

import pytest

import task_actions as ta
import task_bot as tb
import task_log as tl

OWN = "igor.test@gmail.com"
ALIAS = "igor@clearerthinking.org"
TASK = "igor.test+claude@gmail.com"
JANE = "jane.doe@example.com"
REAL_TASK_ADDRESS = tb.task_address     # the fixture below replaces it on the module


@pytest.fixture(autouse=True)
def addresses(monkeypatch):
    monkeypatch.setattr(tb, "OWN_ADDRESS", OWN)
    monkeypatch.setattr(tb, "DEFAULT_FROM", ALIAS)
    monkeypatch.setattr(tb, "EXTRA_ALIASES", [])
    monkeypatch.setattr(tb, "task_address", lambda own=OWN: TASK)


def b64(text):
    return base64.urlsafe_b64encode(text.encode()).decode()


def gmail_msg(mid, labels, headers, body="", internal=1000, thread="t1", mime="text/plain"):
    return {"id": mid, "threadId": thread, "labelIds": labels, "internalDate": str(internal),
            "payload": {"mimeType": mime, "headers": [{"name": k, "value": v} for k, v in headers.items()],
                        "body": {"data": b64(body)}}}


GMAIL_FORWARD = (
    "claude, remove from CT beehiiv\n\n"
    "---------- Forwarded message ---------\n"
    "From: Jane Doe <Jane.Doe@example.com>\n"
    "Date: Tue, Nov 17, 2026 at 3:04 PM\n"
    "Subject: please unsubscribe me\n"
    "To: <info@clearerthinking.org>\n\n"
    "Hi, please take me off your list.\n")


# --- reading the email ------------------------------------------------------------------------
def test_task_address_is_the_plus_claude_form_of_the_own_address():
    assert REAL_TASK_ADDRESS("Someone@Gmail.com") == "someone+claude@gmail.com"


def test_split_instruction_gmail_forward():
    instruction, quoted = tb.split_instruction(GMAIL_FORWARD)
    assert instruction == "claude, remove from CT beehiiv"
    assert quoted.startswith("---------- Forwarded message")
    assert "take me off your list" in quoted


@pytest.mark.parametrize("body, instruction", [
    ("cancel it\n\nBegin forwarded message:\n\nFrom: A <a@x.com>\n\nhello", "cancel it"),
    ("do it\n\n-----Original Message-----\nFrom: a@x.com\nhello", "do it"),
    ("yes, the $99 one\n\nOn Tue, Nov 17, 2026 at 3:04 PM Claude Tasks <i@x.com> wrote:\n> which one?", "yes, the $99 one"),
    # Gmail wraps a long attribution line onto a second line
    ("go ahead\n\nOn Tue, Nov 17, 2026 at 3:04 PM Somebody With A Long Name <long.address@example.com>\nwrote:\n> hi", "go ahead"),
    # Portuguese Gmail
    ("remova\n\n---------- Mensagem encaminhada ---------\nDe: A <a@x.com>\n\noi", "remova"),
    ("sim\n\nEm ter., 17 de nov. de 2026 às 15:04, A <a@x.com> escreveu:\n> qual?", "sim"),
    ("ok\n> quoted line", "ok"),
])
def test_split_instruction_other_clients(body, instruction):
    assert tb.split_instruction(body)[0] == instruction


def test_split_instruction_without_any_quote_is_all_instruction():
    assert tb.split_instruction("unsubscribe bob@example.com please") == ("unsubscribe bob@example.com please", "")
    assert tb.split_instruction("") == ("", "")


def test_split_instruction_empty_note_above_forward():
    instruction, quoted = tb.split_instruction("\n\n---------- Forwarded message ---------\nFrom: A <a@x.com>\n\nhi")
    assert instruction == ""
    assert "a@x.com" in quoted


def test_forwarded_sender_reads_the_first_from_line():
    _, quoted = tb.split_instruction(GMAIL_FORWARD)
    assert tb.forwarded_sender(quoted) == ("Jane Doe", JANE)
    assert tb.forwarded_sender("*From:* Bob <bob@x.com>\n") == ("Bob", "bob@x.com")
    assert tb.forwarded_sender("De: ana@x.com\n") == ("", "ana@x.com")
    assert tb.forwarded_sender("no header here") == ("", "")


def test_full_text_prefers_plain_and_falls_back_to_html():
    plain = gmail_msg("m", [], {}, "hello\r\nthere")["payload"]
    assert tb.full_text(plain) == "hello\nthere"
    page = {"mimeType": "multipart/alternative", "parts": [
        {"mimeType": "text/html", "body": {"data": b64("<style>p{}</style><p>Hi &amp; bye</p><div>line two<br>three</div>")}}]}
    assert tb.full_text(page) == "Hi & bye\nline two\nthree"
    assert tb.full_text({}) == ""


# --- who sent it (the authentication) ---------------------------------------------------------
def test_classify_only_mail_gmail_filed_as_sent_to_the_task_address_is_a_task():
    to_task = {"To": f"Claude <{TASK.upper()}>", "From": OWN}
    assert tb.classify(gmail_msg("a", ["SENT"], to_task), TASK) == "task"
    assert tb.classify(gmail_msg("a", ["SENT", "INBOX"], to_task), TASK) == "task"
    # a stranger writing to the address (even with Igor's name forged in From) is never a task
    assert tb.classify(gmail_msg("b", ["INBOX", "UNREAD"], to_task), TASK) == "received"
    # the bot's own report carries its header
    assert tb.classify(gmail_msg("c", ["SENT", "INBOX"], {**to_task, tb.BOT_HEADER: "report"}), TASK) == "report"
    # an unsent draft, and mail Igor sent to someone else (e.g. the customer reply he sends later)
    assert tb.classify(gmail_msg("d", ["DRAFT"], to_task), TASK) == "draft"
    assert tb.classify(gmail_msg("e", ["SENT"], {"To": JANE}), TASK) == "sent"
    # the task address only in Cc does not make it a task
    assert tb.classify(gmail_msg("f", ["SENT"], {"To": JANE, "Cc": TASK}), TASK) == "sent"


class FakeGmail:
    """Just enough of the Gmail client for find_pending."""

    def __init__(self, messages):
        self.messages_by_id = {m["id"]: m for m in messages}
        self.queries = []

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, userId, q, maxResults):
        self.queries.append(q)
        return _Exec({"messages": [{"id": i} for i in self.messages_by_id]})

    def get(self, userId, id, format):
        return _Exec(self.messages_by_id[id])


class _Exec:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


def test_find_pending_keeps_untaken_tasks_oldest_first_whatever_the_search_returns():
    to_task = {"To": TASK}
    svc = FakeGmail([
        gmail_msg("new", ["SENT"], to_task, internal=300),
        gmail_msg("old", ["SENT"], to_task, internal=100),
        gmail_msg("taken", ["SENT", "Label_7"], to_task, internal=200),
        gmail_msg("stranger", ["INBOX"], to_task, internal=250),
        gmail_msg("report", ["SENT", "Label_7"], {**to_task, tb.BOT_HEADER: "report"}, internal=260),
    ])
    assert [m["id"] for m in tb.find_pending(svc, "Label_7")] == ["old", "new"]
    assert svc.queries == [f"in:sent to:{TASK} newer_than:{tb.LOOKBACK}"]


# --- scope, context, reply targets --------------------------------------------------------------
def task_item(body=GMAIL_FORWARD, mid="m2", internal=2000):
    return tb.parse_task(gmail_msg(mid, ["SENT"], {"To": TASK, "Subject": "Fwd: please unsubscribe me",
                                                   "Message-ID": "<fwd@mail>"}, body, internal))


def test_scope_is_every_address_igor_sent_including_earlier_task_emails():
    item = task_item("yes, also tell angel@overcome.example\n\nOn Tue, Nov 17, 2026 at 3:04 PM Bot <b@x.com> wrote:\n> q")
    earlier = [{"kind": "task", "instruction": "cancel", "quoted": "From: Jane <Jane.Doe@example.com>"},
               {"kind": "report", "text": "I could also email mallory@evil.example"}]
    scope = tb.scope_emails(item, earlier)
    assert JANE in scope and "angel@overcome.example" in scope
    assert "mallory@evil.example" not in scope       # the bot's own reports never widen the scope


def test_earlier_context_keeps_tasks_and_reports_before_this_message():
    thread = [
        gmail_msg("c1", ["INBOX"], {"From": f"Jane <{JANE}>", "To": ALIAS}, "please cancel", internal=100),
        gmail_msg("m1", ["SENT"], {"To": TASK}, GMAIL_FORWARD, internal=200),
        gmail_msg("r1", ["SENT"], {"To": TASK, tb.BOT_HEADER: "report"}, "Which subscription?", internal=300),
        gmail_msg("m2", ["SENT"], {"To": TASK}, "the $99 one", internal=400),
        gmail_msg("later", ["SENT"], {"To": TASK}, "something newer", internal=500),
    ]
    item = tb.parse_task(thread[3])
    earlier = tb.earlier_context(thread, item, TASK)
    assert [e["kind"] for e in earlier] == ["task", "report"]
    assert earlier[0]["instruction"] == "claude, remove from CT beehiiv"
    assert earlier[1]["text"] == "Which subscription?"


def test_reply_targets_point_at_the_latest_message_of_each_outside_sender():
    thread = [
        gmail_msg("c1", ["INBOX"], {"From": f"Jane <{JANE}>", "To": ALIAS, "Subject": "cancel please",
                                    "Message-ID": "<one@x>"}, internal=100),
        gmail_msg("c2", ["INBOX"], {"From": f"Jane <{JANE}>", "To": f"Igor <{ALIAS}>", "Subject": "Re: cancel please",
                                    "Message-ID": "<two@x>", "References": "<one@x>"}, internal=150),
        gmail_msg("m1", ["SENT"], {"From": OWN, "To": TASK}, internal=200),
    ]
    targets = tb.reply_targets(thread, [OWN, ALIAS, TASK])
    assert list(targets) == [JANE]
    assert targets[JANE] == {"thread_id": "t1", "message_id": "<two@x>", "references": "<one@x>",
                             "subject": "Re: cancel please", "written_to": ALIAS}


def test_user_prompt_fences_other_peoples_text_and_the_subject():
    item = task_item()
    prompt = tb.user_prompt(item, [], "=====B=====")
    head, _, fenced = prompt.partition("MATERIAL IGOR FORWARDED")
    assert "IGOR'S INSTRUCTION\nclaude, remove from CT beehiiv" in head
    assert "please unsubscribe me" not in head            # the stranger's subject is not above the fence
    assert fenced.count("=====B=====") == 2
    assert "Subject line: Fwd: please unsubscribe me" in fenced and "take me off your list" in fenced


def test_system_prompt_lists_tools_contacts_and_the_quoting_rule(monkeypatch):
    monkeypatch.setattr(tb, "tool_prefix", lambda: "python task_bot.py --tool")
    text = tb.system_prompt([{"name": "Angel", "email": "angel@overcome.example", "notes": "coach management"}], "today")
    for t in ta.TOOLS:
        assert f"- {t['name']}:" in text
    assert "python task_bot.py --tool <tool_name>" in text
    assert "- Angel <angel@overcome.example>: coach management" in text
    assert "\\u0027" in text


# --- guardrails (task_actions) ------------------------------------------------------------------
@pytest.fixture
def ctx_file(tmp_path, monkeypatch):
    path = tmp_path / "context.json"
    monkeypatch.setenv(ta.CONTEXT_ENV, str(path))

    def make(**kw):
        defaults = dict(task_id="m1", allowed_emails=[JANE], own_addresses=[OWN, ALIAS, TASK],
                        contacts=[{"name": "Angel", "email": "angel@overcome.example", "send_from": OWN, "notes": ""}],
                        default_from=ALIAS, from_name="Igor Test")
        defaults.update(kw)
        ta.save_context(ta.new_context(**defaults))
        return path
    return make


def test_find_emails_and_clean_email():
    assert ta.find_emails("Write to <Jane.Doe@Example.com>, or mailto:bob@mail.example.co.uk. Not a@b") == [
        JANE, "bob@mail.example.co.uk"]
    assert ta.clean_email("  Jane.Doe@example.com ") == JANE
    for bad in ("jane", "a@b.com, c@d.com", "x@y.com' OR 1=1", "", None):
        with pytest.raises(ta.Refused):
            ta.clean_email(bad)


def test_scope_refuses_people_not_named_in_the_email_and_igor_himself(ctx_file):
    ctx_file()
    ctx = ta.load_context()
    ta.require_in_scope(ctx, JANE)
    with pytest.raises(ta.Refused, match="does not appear in Igor's email"):
        ta.require_in_scope(ctx, "victim@example.com")
    with pytest.raises(ta.Refused, match="Igor's own address"):
        ta.require_in_scope(ctx, OWN)
    assert OWN not in ta.new_context("x", [OWN, JANE], [OWN])["allowed_emails"]


def test_budget_refuses_once_spent(ctx_file):
    ctx_file()
    ctx = ta.load_context()
    for _ in range(ta.BUDGET["cancel_subscription"]):
        ta.spend(ctx, "cancel_subscription")
    with pytest.raises(ta.Refused, match="limit of 2"):
        ta.spend(ctx, "cancel_subscription")


def test_recipient_kind(ctx_file):
    ctx_file()
    ctx = ta.load_context()
    assert ta.recipient_kind(ctx, JANE) == "person"
    assert ta.recipient_kind(ctx, "angel@overcome.example") == "contact"
    assert ta.recipient_kind(ctx, ALIAS) == "igor"
    with pytest.raises(ta.Refused):
        ta.recipient_kind(ctx, "press@newspaper.example")


def test_clean_copy_removes_em_dashes():
    assert ta.clean_copy("Done \u2014 access ends Dec 3\u2014then nothing") == "Done, access ends Dec 3, then nothing"
    assert ta.clean_copy("pages 3\u20135 stay") == "pages 3\u20135 stay"      # a number range keeps its en dash
    assert ta.clean_copy("this \u2013 that") == "this, that"


# By hand: 1764720000 = 2025-12-03 00:00:00 UTC (20425 days after the epoch, x 86400).
DEC_3_2025 = 1764720000


def stripe_sub(**over):
    sub = {"id": "sub_1", "status": "active", "start_date": DEC_3_2025 - 30 * 86400, "cancel_at_period_end": False,
           "cancel_at": None, "ended_at": None,
           "items": {"data": [{"current_period_end": DEC_3_2025,
                               "price": {"unit_amount": 9900, "currency": "usd", "product": "prod_nav",
                                         "recurring": {"interval": "month", "interval_count": 1}}}]}}
    sub.update(over)
    return sub


def test_describe_subscription_by_hand():
    d = ta.describe_subscription(stripe_sub(), "CT Plus - Navigator")
    assert d["current_period_ends"] == "2025-12-03" and d["current_period_ends_text"] == "December 3, 2025"
    assert d["price"] == "$99/month" and d["live"] is True and d["set_to_cancel"] is False
    assert d["access_until"] is None
    assert d["started"] == "2025-11-03"
    # older API shape: the period end sits on the subscription itself
    old = stripe_sub(current_period_end=DEC_3_2025 + 86400)
    assert ta.describe_subscription(old)["current_period_ends"] == "2025-12-04"
    cancelling = ta.describe_subscription(stripe_sub(cancel_at_period_end=True, cancel_at=DEC_3_2025))
    assert cancelling["set_to_cancel"] is True and cancelling["access_until_text"] == "December 3, 2025"
    ended = ta.describe_subscription(stripe_sub(status="canceled", ended_at=DEC_3_2025))
    assert ended["live"] is False and ended["ended"] == "2025-12-03"


def test_price_text_forms():
    def with_price(**p):
        return {"items": {"data": [{"price": p}]}}
    assert ta.price_text(with_price(unit_amount=950, currency="usd", recurring={"interval": "month"})) == "$9.50/month"
    assert ta.price_text(with_price(unit_amount=17900, currency="usd", recurring={"interval": "month", "interval_count": 3})) == "$179 every 3 months"
    assert ta.price_text(with_price(unit_amount=2000, currency="eur", recurring={"interval": "year"})) == "20.00 EUR/year"
    assert ta.price_text({"items": {"data": []}}) == ""


class FakeStripeSubscription:
    def __init__(self):
        self.modified = []

    def modify(self, sub_id, **kw):
        self.modified.append((sub_id, kw))
        return stripe_sub(id=sub_id, cancel_at_period_end=True, cancel_at=DEC_3_2025)


@pytest.fixture
def fake_stripe(monkeypatch):
    class Stripe:
        Subscription = FakeStripeSubscription()
    stripe = Stripe()
    subs = {"list": [ta.describe_subscription(stripe_sub(), "CT Plus - Navigator")]}
    monkeypatch.setattr(ta, "_stripe", lambda write=False: stripe)
    monkeypatch.setattr(ta, "stripe_subscriptions", lambda s, email: [dict(x) for x in subs["list"]])
    return stripe, subs


def test_cancel_sets_period_end_cancellation_and_records_it(ctx_file, fake_stripe):
    ctx_file()
    stripe, _ = fake_stripe
    out = ta.tool_cancel_subscription(email=JANE.upper())
    assert out["result"] == "cancelled_at_period_end" and out["access_until"] == "2025-12-03"
    assert stripe.Subscription.modified == [("sub_1", {"cancel_at_period_end": True})]
    ctx = ta.load_context()
    assert ctx["used"] == {"cancel_subscription": 1}
    assert ctx["actions"][0]["changed"] is True
    assert "access until December 3, 2025" in ctx["actions"][0]["text"] and "$99/month" in ctx["actions"][0]["text"]


def test_cancel_refuses_out_of_scope_and_foreign_subscription_ids(ctx_file, fake_stripe):
    ctx_file()
    stripe, _ = fake_stripe
    assert "refused" in ta.tool_cancel_subscription(email="victim@example.com")
    assert "refused" in ta.tool_cancel_subscription(email=JANE, subscription_id="sub_someone_else")
    assert stripe.Subscription.modified == []
    assert [r["tool"] for r in ta.load_context()["refusals"]] == ["cancel_subscription", "cancel_subscription"]


def test_cancel_changes_nothing_when_ambiguous_missing_or_already_cancelling(ctx_file, fake_stripe):
    ctx_file()
    stripe, subs = fake_stripe
    subs["list"] = [ta.describe_subscription(stripe_sub(id="sub_1"), "A"), ta.describe_subscription(stripe_sub(id="sub_2"), "B")]
    assert ta.tool_cancel_subscription(email=JANE)["result"] == "several_live_subscriptions"
    subs["list"] = [ta.describe_subscription(stripe_sub(status="canceled"), "A")]
    assert ta.tool_cancel_subscription(email=JANE)["result"] == "no_live_subscription"
    subs["list"] = [ta.describe_subscription(stripe_sub(cancel_at_period_end=True, cancel_at=DEC_3_2025), "A")]
    assert ta.tool_cancel_subscription(email=JANE)["result"] == "already_set_to_cancel"
    assert stripe.Subscription.modified == []
    assert ta.load_context()["used"] == {}                 # nothing was spent on calls that changed nothing
    # with an id, the chosen one of several is cancelled
    subs["list"] = [ta.describe_subscription(stripe_sub(id="sub_1"), "A"), ta.describe_subscription(stripe_sub(id="sub_2"), "B")]
    assert ta.tool_cancel_subscription(email=JANE, subscription_id="sub_2")["result"] == "cancelled_at_period_end"
    assert stripe.Subscription.modified == [("sub_2", {"cancel_at_period_end": True})]


def test_cancel_dry_run_never_calls_stripe(ctx_file, fake_stripe):
    ctx_file(dry_run=True)
    stripe, _ = fake_stripe
    out = ta.tool_cancel_subscription(email=JANE)
    assert out["dry_run"] is True and out["access_until_text"] == "December 3, 2025"
    assert stripe.Subscription.modified == []
    assert "dry run" in ta.load_context()["actions"][0]["text"]


@pytest.fixture
def fake_beehiiv(monkeypatch):
    state = {"sub": {"id": "sub_abc", "status": "active", "created": DEC_3_2025}, "puts": [], "after": "inactive"}

    def subscriber(email):
        return dict(state["sub"]) if state["sub"] else None

    class Resp:
        status_code = 200

        def raise_for_status(self):
            return None

    def request(method, url, headers, **kw):
        state["puts"].append((method, url, kw.get("json")))
        state["sub"]["status"] = state["after"]
        return Resp()

    monkeypatch.setattr(ta, "beehiiv_subscriber", subscriber)
    monkeypatch.setattr(ta, "_beehiiv_request", request)
    monkeypatch.setattr(ta, "_beehiiv", lambda: ("https://api.example/subs", {}))
    return state


def test_unsubscribe_puts_the_flag_and_confirms_by_reading_back(ctx_file, fake_beehiiv):
    ctx_file()
    assert ta.tool_unsubscribe_newsletter(email=JANE) == {"result": "unsubscribed", "status_after": "inactive"}
    assert fake_beehiiv["puts"] == [("PUT", "https://api.example/subs/sub_abc", {"unsubscribe": True})]
    assert "confirmed" in ta.load_context()["actions"][0]["text"]


def test_unsubscribe_reports_unconfirmed_missing_and_already_out(ctx_file, fake_beehiiv):
    ctx_file()
    fake_beehiiv["after"] = "active"                        # beehiiv said OK but nothing changed
    out = ta.tool_unsubscribe_newsletter(email=JANE)
    assert out["result"] == "not_confirmed"
    assert ta.load_context()["actions"][0]["problem"] is True
    fake_beehiiv["sub"]["status"] = "inactive"
    assert ta.tool_unsubscribe_newsletter(email=JANE)["result"] == "already_unsubscribed"
    fake_beehiiv["sub"] = None
    assert ta.tool_unsubscribe_newsletter(email=JANE)["result"] == "not_found"
    assert len(fake_beehiiv["puts"]) == 1
    assert "refused" in ta.tool_unsubscribe_newsletter(email="victim@example.com")


def test_unsubscribe_dry_run_changes_nothing(ctx_file, fake_beehiiv):
    ctx_file(dry_run=True)
    assert ta.tool_unsubscribe_newsletter(email=JANE)["dry_run"] is True
    assert fake_beehiiv["puts"] == []


def test_build_draft_replies_in_the_persons_conversation_from_the_address_they_wrote_to(ctx_file):
    ctx_file(reply_targets={JANE: {"thread_id": "t9", "message_id": "<two@x>", "references": "<one@x>",
                                   "subject": "Fwd: Re: cancel please", "written_to": OWN}})
    ctx = ta.load_context()
    msg, thread = ta.build_draft(ctx, JANE, "Your cancellation", "Hi Jane \u2014 it’s done.\n\nIgor")
    assert thread == "t9"
    assert msg["Subject"] == "Re: cancel please"            # keeps the conversation's subject
    assert msg["In-Reply-To"] == "<two@x>" and msg["References"] == "<one@x> <two@x>"
    assert msg["From"] == f"Igor Test <{OWN}>" and msg["To"] == JANE
    assert msg.get_payload(decode=True).decode() == "Hi Jane, it’s done.\n\nIgor\n"


def test_build_draft_new_email_uses_contact_or_default_sender(ctx_file):
    ctx_file()
    ctx = ta.load_context()
    msg, thread = ta.build_draft(ctx, "angel@overcome.example", "Navigator cancellation", "Hi Angel")
    assert thread is None and msg["From"] == f"Igor Test <{OWN}>" and msg["Subject"] == "Navigator cancellation"
    assert "In-Reply-To" not in msg
    msg, _ = ta.build_draft(ctx, JANE, "Done", "Hi")
    assert msg["From"] == f"Igor Test <{ALIAS}>"            # no thread, no contact: the default alias


def test_draft_tool_refuses_strangers_and_dry_run_creates_nothing(ctx_file):
    ctx_file(dry_run=True)
    assert "refused" in ta.tool_draft_email(to="press@newspaper.example", subject="x", body="y")
    assert "refused" in ta.tool_draft_email(to=JANE, subject="", body="y")
    out = ta.tool_draft_email(to=JANE, subject="Done", body="It's done.")
    assert out == {"result": "drafted", "dry_run": True, "from": f"Igor Test <{ALIAS}>", "subject": "Done"}
    ctx = ta.load_context()
    assert ctx["actions"][0]["preview"] == "It's done.\n" and "draft" not in ctx["actions"][0]


def test_finish_records_a_valid_outcome_only(ctx_file):
    ctx_file()
    assert "refused" in ta.tool_finish(status="great")
    assert ta.tool_finish(status="Needs_You", about="Jane <j@x.com>", summary="Two subscriptions \u2014 which?") == {"saved": True}
    assert ta.load_context()["outcome"] == {"status": "needs_you", "about": "Jane <j@x.com>",
                                            "summary": "Two subscriptions, which?"}


def test_tool_mode_dispatch_prints_json(ctx_file, monkeypatch, capsys):
    ctx_file()
    monkeypatch.setattr(tb.sys, "argv", ["task_bot.py", "--tool", "finish", '{"status": "done", "summary": "ok"}'])
    assert tb.main() == 0
    assert json.loads(capsys.readouterr().out) == {"saved": True}
    monkeypatch.setattr(tb.sys, "argv", ["task_bot.py", "--tool", "refund_everyone", "{}"])
    assert tb.main() == 0
    assert "unknown tool" in json.loads(capsys.readouterr().out)["error"]


# --- outcome and report -------------------------------------------------------------------------
def test_derive_status():
    draft = {"tool": "draft_email", "text": "Draft", "draft": {"draft_id": "d1"}}
    done = {"outcome": {"status": "done"}, "actions": [{"tool": "x", "text": "did"}]}
    assert tb.derive_status(done) == tl.DONE
    assert tb.derive_status({**done, "actions": [draft]}) == tl.DRAFTS_WAITING
    assert tb.derive_status({"outcome": {"status": "needs_you"}, "actions": [draft]}) == tl.NEEDS_YOU
    assert tb.derive_status({"outcome": {"status": "cannot_do"}, "actions": []}) == tl.NEEDS_YOU
    assert tb.derive_status({"outcome": None, "actions": []}) == tl.NEEDS_YOU          # the model did nothing
    assert tb.derive_status({"outcome": {"status": "done"}, "actions": [{"text": "x", "problem": True}]}) == tl.NEEDS_YOU
    assert tb.derive_status(done, error="RuntimeError: boom") == tl.FAILED


def test_format_report_is_built_from_the_record_not_the_models_words():
    ctx = {"actions": [{"tool": "cancel_subscription", "text": "Stripe: Navigator set to cancel."},
                       {"tool": "draft_email", "text": 'Email drafted in Gmail: to j@x.com, "Re: cancel".', "draft": {"draft_id": "d"}}],
           "refusals": [{"tool": "cancel_subscription", "why": "not in scope"}]}
    text = tb.format_report("All done \u2014 two things.", ctx, tl.DRAFTS_WAITING, "12")
    assert text.startswith("All done, two things.")
    assert "- Stripe: Navigator set to cancel." in text and "1 draft is waiting in Gmail" in text
    assert "Blocked by the safety limits:\n- cancel_subscription: not in scope" in text
    assert f"Status: Drafts waiting | Task #12 | All tasks: {tb.PAGE_URL}" in text
    empty = tb.format_report("", {"actions": []}, tl.FAILED, error="RuntimeError: boom")
    assert empty.startswith("This task did not finish: RuntimeError: boom") and "- Nothing was changed." in empty


def test_draft_state_and_summary():
    draft = {"to": JANE, "created_ms": 10_000_000}
    waiting = [{"labels": ["DRAFT"], "to": f"Jane <{JANE}>", "internal_ms": 10_000_000, "bot": False}]
    sent = [{"labels": ["SENT"], "to": JANE, "internal_ms": 10_500_000, "bot": False}]
    # mail Igor sent that person BEFORE the draft existed, the forward itself, and the bot's report do not count
    noise = [{"labels": ["SENT"], "to": JANE, "internal_ms": 1_000, "bot": False},
             {"labels": ["SENT"], "to": TASK, "internal_ms": 10_400_000, "bot": False},
             {"labels": ["SENT", "INBOX"], "to": TASK, "internal_ms": 10_600_000, "bot": True}]
    assert tb.draft_state(waiting + noise, draft) == "waiting"
    assert tb.draft_state(sent + noise, draft) == "sent"
    assert tb.draft_state(noise, draft) == "discarded"
    assert tb.draft_state([], draft) == "discarded"
    assert tb.drafts_summary(["waiting", "waiting"]) == "2 waiting"
    assert tb.drafts_summary(["waiting", "sent"]) == "1 of 2 still waiting"
    assert tb.drafts_summary(["sent", "sent", "discarded"]) == "2 sent, 1 discarded"


# --- the whole task, with every outside call faked ----------------------------------------------
class FakeLog:
    def __init__(self):
        self.rows = {}

    def upsert(self, record):
        key = record[tl.KEY_COLUMN]
        self.rows[key] = {**self.rows.get(key, {"Task": str(len(self.rows) + 1)}), **record}
        return self.rows[key]


@pytest.fixture
def wired(monkeypatch):
    calls = {"labels": [], "reports": []}
    thread = [
        gmail_msg("c1", ["INBOX"], {"From": f"Jane Doe <{JANE}>", "To": ALIAS, "Subject": "please unsubscribe me",
                                    "Message-ID": "<c1@x>"}, "Hi, please take me off your list.", internal=100),
        gmail_msg("m1", ["SENT"], {"To": TASK, "Subject": "Fwd: please unsubscribe me", "Message-ID": "<m1@x>"},
                  GMAIL_FORWARD, internal=200),
    ]
    monkeypatch.setattr(tb, "thread_of", lambda svc, tid: thread)
    monkeypatch.setattr(tb, "modify_labels", lambda svc, mid, add=(), remove=(): calls["labels"].append((mid, list(add), list(remove))))
    monkeypatch.setattr(tb, "send_report", lambda svc, item, body, label: calls["reports"].append(body))
    return thread, calls


def test_process_runs_the_task_labels_first_logs_and_reports(wired, monkeypatch):
    thread, calls = wired
    seen = {}

    def fake_model(system, user):
        seen["labelled_before_model"] = list(calls["labels"])
        ctx = ta.load_context()                                  # the tool child would do this
        seen["scope"] = ctx["allowed_emails"]
        seen["reply_target"] = ctx["reply_targets"][JANE]["message_id"]
        ta.record(ctx, "unsubscribe_newsletter", f"beehiiv: {JANE} unsubscribed from the newsletter (confirmed).", changed=True)
        ctx["outcome"] = {"status": "done", "about": f"Jane Doe <{JANE}>", "summary": "Unsubscribed."}
        ta.save_context(ctx)
        return "Jane is off the list."

    monkeypatch.setattr(tb, "run_model", fake_model)
    log = FakeLog()
    status = tb.process(object(), thread[1], {tb.LABEL_TAKEN: "L1", tb.LABEL_DRAFTS: "L2"}, log, [], dry_run=False)
    assert status == tl.DONE
    # at most once: label first, then act; Igor's own forward leaves the inbox
    assert seen["labelled_before_model"] == [("m1", ["L1"], ["INBOX", "UNREAD"])]
    assert seen["scope"] == ["info@clearerthinking.org", JANE] and seen["reply_target"] == "<c1@x>"
    row = log.rows["m1"]
    assert row["Status"] == tl.DONE and row["About"] == f"Jane Doe <{JANE}>" and row["Summary"] == "Unsubscribed."
    assert row["Instruction"] == "claude, remove from CT beehiiv" and row["Received (UTC)"] == "1970-01-01 00:00:00"
    assert "Jane is off the list." in calls["reports"][0] and "Status: Done | Task #1" in calls["reports"][0]
    assert ta.CONTEXT_ENV not in tb.os.environ


def test_process_reports_a_failed_model_run_and_keeps_what_was_done(wired, monkeypatch):
    thread, calls = wired

    def broken_model(system, user):
        ctx = ta.load_context()
        ta.record(ctx, "cancel_subscription", "Stripe: Navigator set to cancel.", changed=True)
        ta.save_context(ctx)
        raise RuntimeError("Claude Code exited 1")

    monkeypatch.setattr(tb, "run_model", broken_model)
    log = FakeLog()
    status = tb.process(object(), thread[1], {tb.LABEL_TAKEN: "L1", tb.LABEL_DRAFTS: "L2"}, log, [], dry_run=False)
    assert status == tl.FAILED and log.rows["m1"]["Status"] == tl.FAILED
    assert calls["reports"][0].startswith("This task did not finish: RuntimeError: Claude Code exited 1")
    assert "- Stripe: Navigator set to cancel." in calls["reports"][0]


def test_process_without_an_instruction_asks_instead_of_running_the_model(wired, monkeypatch):
    thread, calls = wired
    monkeypatch.setattr(tb, "run_model", lambda *a: pytest.fail("the model must not run"))
    bare = gmail_msg("m1", ["SENT"], {"To": TASK, "Subject": "Fwd: x"},
                     "---------- Forwarded message ---------\nFrom: Jane <jane.doe@example.com>\n\nhi", internal=200)
    log = FakeLog()
    assert tb.process(object(), bare, {tb.LABEL_TAKEN: "L1", tb.LABEL_DRAFTS: "L2"}, log, [], dry_run=False) == tl.NEEDS_YOU
    assert "no instruction above the forwarded email" in calls["reports"][0]


def test_process_dry_run_touches_nothing(wired, monkeypatch, capsys):
    thread, calls = wired
    monkeypatch.setattr(tb, "IN_CI", False)

    def fake_model(system, user):
        assert ta.load_context()["dry_run"] is True
        return "would do it"

    monkeypatch.setattr(tb, "run_model", fake_model)
    log = FakeLog()
    tb.process(object(), thread[1], {tb.LABEL_TAKEN: "", tb.LABEL_DRAFTS: ""}, log, [], dry_run=True)
    assert calls == {"labels": [], "reports": []} and log.rows == {}
    assert "DRY RUN" in capsys.readouterr().out


def test_process_dry_run_in_ci_prints_no_details(wired, monkeypatch, capsys):
    thread, _ = wired
    monkeypatch.setattr(tb, "IN_CI", True)
    monkeypatch.setattr(tb, "run_model", lambda s, u: f"private note about {JANE}")
    tb.process(object(), thread[1], {tb.LABEL_TAKEN: "", tb.LABEL_DRAFTS: ""}, None, [], dry_run=True)
    out = capsys.readouterr()
    assert JANE not in out.out and JANE not in out.err


# --- the log (task_log) -------------------------------------------------------------------------
def test_rows_to_records_and_back():
    values = [tl.COLUMNS, ["1", "2026-11-18 10:00:00", "Done", "remove them"], [], ["2", "", "Running"]]
    recs = tl.rows_to_records(values)
    assert [r["_row"] for r in recs] == [2, 4]
    assert recs[0]["Instruction"] == "remove them" and recs[0]["Summary"] == ""
    assert tl.record_to_row({"Task": "3", "Status": "Done", "Summary": "x" * 9000}, ["Task", "Status", "Summary"]) == [
        "3", "Done", "x" * tl.CELL_LIMIT]
    assert tl.next_task_number(recs) == 3 and tl.next_task_number([]) == 1
    assert tl.rows_to_records([]) == []


def test_column_letter():
    assert [tl.column_letter(i) for i in (0, 11, 25, 26, 27)] == ["A", "L", "Z", "AA", "AB"]


def test_is_stale_running():
    now = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)
    def at(minutes_ago, status=tl.RUNNING):
        return {"Status": status, "Updated (UTC)": (now - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%d %H:%M:%S")}
    assert tl.is_stale_running(at(31), now) is True
    assert tl.is_stale_running(at(29), now) is False
    assert tl.is_stale_running(at(500, tl.DONE), now) is False
    assert tl.is_stale_running({"Status": tl.RUNNING, "Updated (UTC)": "garbage"}, now) is True


def test_contacts_from_rows_skips_blank_and_invalid():
    values = [tl.CONTACT_COLUMNS, ["Angel", " Angel@Overcome.example ", "Igor.Test@gmail.com", "coach management"],
              ["No email", "", "", ""], ["Bad", "not-an-address", "", ""]]
    assert tl.contacts_from_rows(values) == [{"name": "Angel", "email": "angel@overcome.example",
                                              "send_from": "igor.test@gmail.com", "notes": "coach management"}]


def test_parse_draft_data_tolerates_garbage():
    assert tl.parse_draft_data({"Draft data": '[{"draft_id": "d1"}]'}) == [{"draft_id": "d1"}]
    assert tl.parse_draft_data({"Draft data": "not json"}) == []
    assert tl.parse_draft_data({}) == []


class FakeSheets:
    """Records the calls TaskLog makes; serves `values` for reads."""

    def __init__(self, values):
        self.values_data = values
        self.calls = []

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, spreadsheetId, range):
        if range.endswith("!1:1"):
            return _Exec({"values": self.values_data[:1]})
        return _Exec({"values": self.values_data})

    def update(self, **kw):
        self.calls.append(("update", kw))
        return _Exec({})

    def append(self, **kw):
        self.calls.append(("append", kw))
        return _Exec({})


def test_tasklog_upsert_appends_new_and_updates_existing_as_raw_text(monkeypatch):
    monkeypatch.setattr(tl, "utc_now", lambda: "2026-11-18 12:00:00")
    header = ["Task", "Status", "Instruction", "Updated (UTC)", "Message ID"]
    svc = FakeSheets([header, ["1", "Done", "first", "x", "m1"]])
    log = tl.TaskLog("sheet", service=svc)
    new = log.upsert({"Message ID": "m2", "Status": "Running", "Instruction": "=HYPERLINK(evil)"})
    assert new["Task"] == "2"
    kind, kw = svc.calls[0]
    assert kind == "append" and kw["valueInputOption"] == "RAW"            # "=..." stays text, never a formula
    assert kw["body"]["values"] == [["2", "Running", "=HYPERLINK(evil)", "2026-11-18 12:00:00", "m2"]]
    log.upsert({"Message ID": "m1", "Status": "Failed"})
    kind, kw = svc.calls[1]
    assert kind == "update" and kw["range"] == "Tasks!A2:E2" and kw["valueInputOption"] == "RAW"
    assert kw["body"]["values"] == [["1", "Failed", "first", "2026-11-18 12:00:00", "m1"]]   # other cells kept
