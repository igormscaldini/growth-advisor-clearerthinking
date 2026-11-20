"""The task bot's action catalogue: the only things an emailed instruction can make happen.

task_bot.py hands Igor's email to a headless Claude session whose single tool is
`python task_bot.py --tool <name> '<json>'`, which lands here. The email usually contains text
written by a stranger (the forwarded message), so nothing in this file trusts the model's
judgement for safety. The limits are enforced in code:

  * every action is scoped to people NAMED IN IGOR'S EMAIL (`allowed_emails` in the context);
  * each kind of action has a small per-task budget (BUDGET);
  * NOTHING CHANGES BEFORE IGOR SAYS YES (his choice, 2026-11-20). A new task runs in "plan" mode:
    the model may only look things up and describe the changes it would make (propose_changes,
    which checks each one against live data). task_bot.py emails Igor that plan; only a plain "yes"
    reply puts the next run in "execute" mode, where task_bot.py itself (not the model) calls the
    change tools with exactly the approved arguments. Every change tool calls `require_approved`,
    which refuses anything outside the approved plan and consumes each approved item once;
  * a subscription is only ever set to cancel at period end (reversible until that date), and
    only one that belongs to a Stripe customer with that person's address;
  * a refund is only ever made on a payment of that person, up to what is left unrefunded on it
    (Igor: no cap beyond the charge), with an idempotency key so a repeated run cannot pay twice.
    No immediate cancellations and no deletions exist here;
  * emails are never sent: draft_email leaves a Gmail draft for Igor to review and send
    (his choice, 2026-11-18), addressed only to those people, a contact from the task log's
    Contacts tab, or Igor himself;
  * every action, refusal and draft is written to the task context file, and the report Igor
    gets is built from that record, not from what the model says it did.

The context file lives outside the repository for the length of one task (path in the
TASK_BOT_CONTEXT env var). The repo and its Actions logs are PUBLIC: nothing here prints.
"""
from __future__ import annotations

import base64
import functools
import json
import os
import re
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

CONTEXT_ENV = "TASK_BOT_CONTEXT"
STRIPE_WRITE_ENV = "STRIPE_TASKBOT_KEY"   # restricted key: Subscriptions + Refunds write (the shared key is read-only)
BEEHIIV_BASE = "https://api.beehiiv.com/v2"

# Per task (one emailed instruction). Small on purpose: a task is about one person, sometimes two.
BUDGET = {"lookup_person": 8, "lookup_payments": 8, "unsubscribe_newsletter": 3, "cancel_subscription": 2,
          "refund_payment": 3, "draft_email": 4}
# The account changes. Each needs Igor's yes first; drafts do not (nothing leaves until he sends them).
GATED = ("unsubscribe_newsletter", "cancel_subscription", "refund_payment")
# The arguments that identify one change: what the plan stores and what the approval is matched on.
CHANGE_KEYS = {"unsubscribe_newsletter": ("email",), "cancel_subscription": ("email", "subscription_id"),
               "refund_payment": ("email", "charge_id", "amount_cents")}
PLAN, EXECUTE = "plan", "execute"
LIVE_STATUSES = ("active", "trialing", "past_due", "unpaid", "paused")
OUTCOMES = ("done", "needs_you", "cannot_do")

EMAIL_FIND_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")


class Refused(Exception):
    """A guardrail said no. The message goes back to the model and into the task record."""


class Invalid(Exception):
    """A proposed change does not match live data (already unsubscribed, no such payment...). The
    message goes back to the model so it can fix the plan; it is not a safety event, so it is not
    listed in Igor's report."""


# --- context (the per-task record shared by the bot and its tool child processes) -----------
def new_context(task_id: str, allowed_emails, own_addresses, contacts=None, reply_targets=None,
                default_from: str = "", from_name: str = "", dry_run: bool = False,
                mode: str = PLAN, approved=None, planned_drafts=None) -> dict:
    own = sorted({norm(a) for a in own_addresses if a})
    return {
        "task_id": task_id,
        "dry_run": bool(dry_run),
        "own_addresses": own,
        "allowed_emails": sorted({norm(e) for e in allowed_emails if e} - set(own)),
        "contacts": contacts or [],
        "reply_targets": reply_targets or {},
        "default_from": default_from,
        "from_name": from_name,
        "mode": EXECUTE if mode == EXECUTE else PLAN,
        "approved": [{**c, "done": False} for c in (approved or [])],   # execute mode: Igor's yes
        "planned_drafts": list(planned_drafts or []),
        "plan": [],             # plan mode: the changes proposed for Igor's yes
        "drafts_plan": [],
        "used": {},
        "actions": [],
        "refusals": [],
        "outcome": None,
    }


def context_path() -> Path:
    path = os.getenv(CONTEXT_ENV, "").strip()
    if not path:
        raise RuntimeError(f"{CONTEXT_ENV} is not set: tools only run inside a task")
    return Path(path)


def load_context() -> dict:
    return json.loads(context_path().read_text(encoding="utf-8"))


def save_context(ctx: dict) -> None:
    path = context_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ctx, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def tool(fn):
    """Load the task context, run the tool, always save the context back. A guardrail refusal
    becomes a {"refused": ...} result (and is recorded) instead of an exception."""
    @functools.wraps(fn)
    def wrapper(**kwargs):
        ctx = load_context()
        try:
            return fn(ctx, **kwargs)
        except Refused as r:
            ctx["refusals"].append({"tool": fn.__name__.replace("tool_", ""), "why": str(r)})
            return {"refused": str(r)}
        except Invalid as e:
            return {"invalid": str(e)}
        finally:
            save_context(ctx)
    return wrapper


# --- guardrails (pure, unit-tested) ---------------------------------------------------------
def norm(email) -> str:
    return str(email or "").strip().lower()


def find_emails(text: str) -> list[str]:
    """Every email address in a text, lower-cased, in order of first appearance."""
    seen: dict[str, None] = {}
    for m in EMAIL_FIND_RE.finditer(text or ""):
        seen.setdefault(m.group(0).lower(), None)
    return list(seen)


def clean_email(value) -> str:
    """A tool argument that must be exactly one plain email address."""
    email = norm(value)
    if not EMAIL_FIND_RE.fullmatch(email):
        raise Refused(f"{value!r} is not a single valid email address")
    return email


def require_in_scope(ctx: dict, email: str) -> None:
    if email in ctx["own_addresses"]:
        raise Refused("that is Igor's own address, not a person a task can act on")
    if email not in ctx["allowed_emails"]:
        raise Refused(
            f"{email} does not appear in Igor's email, so this task may not look them up or change "
            "anything for them. If the person uses another address, ask Igor to reply with it.")


def spend(ctx: dict, kind: str) -> None:
    """Count one use of an action against the task's budget; refuse once it is used up."""
    used = ctx["used"].get(kind, 0)
    if used >= BUDGET[kind]:
        raise Refused(f"this task has already used its limit of {BUDGET[kind]} {kind} calls; "
                      "stop and tell Igor what is left to do")
    ctx["used"][kind] = used + 1


def change_key(kind: str, values: dict) -> tuple:
    """The identity of one change, normalised so "Jane@X.com" and 4500 vs "4500" compare equal."""
    return (kind, *(norm(values.get(k)) for k in CHANGE_KEYS[kind]))


def require_approved(ctx: dict, kind: str, **values) -> dict:
    """The gate every change tool passes first. In plan mode nothing may change; in execute mode
    only a change Igor approved, each one once (the item is consumed here, before the call, so a
    failure half way is never retried by itself)."""
    if ctx.get("mode") != EXECUTE:
        raise Refused("nothing is changed before Igor approves it: describe this change with "
                      "propose_changes instead, and he approves by replying")
    want = change_key(kind, values)
    for item in ctx.get("approved") or []:
        if not item.get("done") and change_key(item["kind"], item) == want:
            item["done"] = True
            return item
    raise Refused("this change is not in the plan Igor approved, so it was not made")


def record(ctx: dict, tool_name: str, text: str, **extra) -> None:
    """One line of the authoritative record of what this task did."""
    ctx["actions"].append({"tool": tool_name, "text": text, "at": int(time.time()),
                           "dry_run": ctx["dry_run"], **extra})


def find_contact(ctx: dict, email: str) -> dict | None:
    for c in ctx.get("contacts") or []:
        if norm(c.get("email")) == email:
            return c
    return None


def recipient_kind(ctx: dict, email: str) -> str:
    """Who a draft may be addressed to: 'igor', 'contact' or 'person'. Anyone else is refused."""
    if email in ctx["own_addresses"]:
        return "igor"
    if find_contact(ctx, email):
        return "contact"
    if email in ctx["allowed_emails"]:
        return "person"
    raise Refused(f"{email} is neither a person named in Igor's email nor one of his saved contacts, "
                  "so no email can be drafted to them")


def clean_copy(text: str) -> str:
    """Igor's rule: no em dashes anywhere. Enforced on everything the bot writes for him."""
    text = re.sub(r"\s*\u2014\s*", ", ", str(text or ""))
    return re.sub(r"\s+\u2013\s+", ", ", text)


# --- Stripe ---------------------------------------------------------------------------------
def _stripe(write: bool = False):
    import stripe

    key = (os.getenv(STRIPE_WRITE_ENV) or "").strip()
    if not key and not write:
        key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    if not key:
        raise RuntimeError(
            f"{STRIPE_WRITE_ENV} is not set. Cancelling needs a Stripe restricted key with "
            "Subscriptions: write (see bots/TASK_BOT.md); the shared key is read-only.")
    stripe.api_key = key
    return stripe


def _plain(obj) -> dict:
    return obj.to_dict() if hasattr(obj, "to_dict") else dict(obj)


def iso_day(ts) -> str | None:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d") if ts else None


def long_day(ts) -> str | None:
    """'December 3, 2026': the form a customer email uses."""
    if not ts:
        return None
    d = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def period_end_ts(sub: dict) -> int | None:
    """End of the current billing period. Stripe moved it from the subscription to its items in
    the 2025 API versions, so read both."""
    if sub.get("current_period_end"):
        return int(sub["current_period_end"])
    ends = [it.get("current_period_end") for it in ((sub.get("items") or {}).get("data") or [])]
    ends = [int(e) for e in ends if e]
    return max(ends) if ends else None


def money(cents, currency="usd") -> str:
    """9900 -> "$99", 950 -> "$9.50", other currencies as "20.00 EUR". Pure."""
    cents = int(cents or 0)
    if (currency or "usd").lower() == "usd":
        return f"${cents / 100:,.2f}".replace(".00", "")
    return f"{cents / 100:,.2f} {str(currency).upper()}"


def price_text(sub: dict) -> str:
    items = (sub.get("items") or {}).get("data") or []
    if not items:
        return ""
    price = items[0].get("price") or {}
    amount = price.get("unit_amount")
    if amount is None:
        return ""
    money_text = money(amount, price.get("currency") or "usd")
    recurring = price.get("recurring") or {}
    every = recurring.get("interval")
    count = recurring.get("interval_count") or 1
    if not every:
        return money_text
    return f"{money_text}/{every}" if count == 1 else f"{money_text} every {count} {every}s"


def describe_subscription(sub: dict, product_name: str = "") -> dict:
    """What the model (and the task record) needs to know about one subscription. Pure."""
    end = period_end_ts(sub)
    cancel_at = sub.get("cancel_at")
    # cancel_at is how newer Stripe API versions express "ends at period end".
    cancelling = bool(sub.get("cancel_at_period_end") or cancel_at)
    return {
        "subscription_id": sub.get("id"),
        "product": product_name or "(unknown product)",
        "price": price_text(sub),
        "status": sub.get("status"),
        "live": sub.get("status") in LIVE_STATUSES,
        "started": iso_day(sub.get("start_date") or sub.get("created")),
        "current_period_ends": iso_day(end),
        "current_period_ends_text": long_day(end),
        "set_to_cancel": cancelling,
        "access_until": iso_day(cancel_at or end) if cancelling else None,
        "access_until_text": long_day(cancel_at or end) if cancelling else None,
        "ended": iso_day(sub.get("ended_at")),
    }


def stripe_customers(stripe, email: str) -> list[dict]:
    """Stripe customers with this address. `Customer.list(email=)` is case-sensitive, so the
    search API (case-insensitive) runs first; the list call is the floor if search is down."""
    found: dict[str, dict] = {}
    try:
        for c in stripe.Customer.search(query=f"email:'{email}'", limit=100).data:
            found[c["id"]] = _plain(c)
    except Exception:  # noqa: BLE001 - search is a convenience; the list calls below are the floor
        pass
    for c in stripe.Customer.list(email=email, limit=100).data:
        found[c["id"]] = _plain(c)
    return [c for c in found.values() if norm(c.get("email")) == email]


def stripe_subscriptions(stripe, email: str) -> list[dict]:
    names: dict[str, str] = {}
    out = []
    for customer in stripe_customers(stripe, email):
        for s in stripe.Subscription.list(customer=customer["id"], status="all", limit=100).auto_paging_iter():
            sub = _plain(s)
            items = (sub.get("items") or {}).get("data") or []
            product_id = ((items[0].get("price") or {}).get("product") if items else None) or ""
            if isinstance(product_id, dict):
                product_id = product_id.get("id", "")
            if product_id and product_id not in names:
                try:
                    names[product_id] = stripe.Product.retrieve(product_id)["name"]
                except Exception:  # noqa: BLE001
                    names[product_id] = ""
            described = describe_subscription(sub, names.get(product_id, ""))
            described["customer_name"] = customer.get("name") or ""
            out.append(described)
    out.sort(key=lambda d: (d["live"], d["started"] or ""), reverse=True)
    return out[:10]


def describe_charge(ch: dict) -> dict:
    """One payment as the model and the plan see it. Pure. Only a succeeded, undisputed charge can
    be refunded, and only what is left on it."""
    amount = int(ch.get("amount") or 0)
    refunded = int(ch.get("amount_refunded") or 0)
    currency = (ch.get("currency") or "usd").lower()
    ok = ch.get("status") == "succeeded" and not ch.get("disputed")
    return {
        "charge_id": ch.get("id"),
        "date": iso_day(ch.get("created")),
        "date_text": long_day(ch.get("created")),
        "amount": money(amount, currency),
        "amount_cents": amount,
        "refunded_cents": refunded,
        "refundable_cents": max(0, amount - refunded) if ok else 0,
        "currency": currency,
        "status": ch.get("status"),
        "disputed": bool(ch.get("disputed")),
        "description": ch.get("description") or "",
        "_created": int(ch.get("created") or 0),
    }


def stripe_charges(stripe, email: str) -> list[dict]:
    """The person's payments, newest first: charges of every Stripe customer with this address,
    plus one-off Checkout payments made without a customer record (the PDF, the Cognitive
    Assessment), found through the Checkout Session's own email."""
    found: dict[str, dict] = {}
    for customer in stripe_customers(stripe, email):
        for c in stripe.Charge.list(customer=customer["id"], limit=25).data:
            found[c["id"]] = _plain(c)
    try:
        sessions = stripe.checkout.Session.list(customer_details={"email": email}, limit=25,
                                                expand=["data.payment_intent.latest_charge"]).data
    except Exception:  # noqa: BLE001 - guest payments are a bonus; customer charges are the floor
        sessions = []
    for s in sessions:
        s = _plain(s)
        if norm((s.get("customer_details") or {}).get("email")) != email:
            continue
        pi = s.get("payment_intent")
        charge = pi.get("latest_charge") if isinstance(pi, dict) else None
        if isinstance(charge, dict) and charge.get("id"):
            found.setdefault(charge["id"], charge)
    out = sorted((describe_charge(c) for c in found.values()), key=lambda d: d["_created"], reverse=True)
    return [{k: v for k, v in d.items() if k != "_created"} for d in out[:25]]


def find_charge(charges: list[dict], charge_id: str) -> dict | None:
    return next((c for c in charges if c["charge_id"] == charge_id), None)


# --- beehiiv --------------------------------------------------------------------------------
def _beehiiv():
    key = (os.getenv("BEEHIIV_API_KEY") or "").strip()
    pub = (os.getenv("BEEHIIV_PUB_CLEARER_THINKING") or "").strip()
    if not key or not pub:
        raise RuntimeError("BEEHIIV_API_KEY / BEEHIIV_PUB_CLEARER_THINKING not set")
    return f"{BEEHIIV_BASE}/publications/{pub}/subscriptions", {
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _beehiiv_request(method: str, url: str, headers: dict, **kwargs):
    """One beehiiv call with a timeout and a short retry on rate limits and server errors."""
    import requests

    resp = None
    for attempt in range(4):
        try:
            resp = requests.request(method, url, headers=headers, timeout=(10, 30), **kwargs)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
            continue
        if resp.status_code not in (429, 500, 502, 503, 504) or attempt == 3:
            return resp
        time.sleep(2 * (attempt + 1))
    return resp


def beehiiv_subscriber(email: str) -> dict | None:
    """The beehiiv subscription for an address, or None when there is none."""
    base, headers = _beehiiv()
    r = _beehiiv_request("GET", f"{base}/by_email/{quote(email, safe='')}", headers)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return (r.json() or {}).get("data") or None


def describe_subscriber(sub: dict | None) -> dict:
    if not sub:
        return {"found": False}
    return {"found": True, "status": sub.get("status"), "subscribed_on": iso_day(sub.get("created")),
            "tier": sub.get("subscription_tier")}


# --- tools ----------------------------------------------------------------------------------
@tool
def tool_lookup_person(ctx, email=None, **_):
    email = clean_email(email)
    require_in_scope(ctx, email)
    spend(ctx, "lookup_person")
    out: dict = {"email": email}
    try:
        out["newsletter"] = describe_subscriber(beehiiv_subscriber(email))
    except Exception as e:  # noqa: BLE001 - one system failing must not hide the other
        out["newsletter"] = {"error": f"{type(e).__name__}: {e}"}
    try:
        out["stripe_subscriptions"] = stripe_subscriptions(_stripe(), email)
    except Exception as e:  # noqa: BLE001
        out["stripe_subscriptions"] = {"error": f"{type(e).__name__}: {e}"}
    return out


@tool
def tool_unsubscribe_newsletter(ctx, email=None, **_):
    email = clean_email(email)
    require_in_scope(ctx, email)
    require_approved(ctx, "unsubscribe_newsletter", email=email)
    sub = beehiiv_subscriber(email)
    if not sub:
        record(ctx, "unsubscribe_newsletter", f"beehiiv: no subscriber with the address {email}; nothing changed.",
               changed=False)
        return {"result": "not_found", "note": "No beehiiv subscriber has this address. They may be "
                "subscribed under another one; ask Igor rather than guessing."}
    if sub.get("status") == "inactive":
        record(ctx, "unsubscribe_newsletter", f"beehiiv: {email} was already unsubscribed; nothing changed.",
               changed=False)
        return {"result": "already_unsubscribed"}
    spend(ctx, "unsubscribe_newsletter")
    if ctx["dry_run"]:
        record(ctx, "unsubscribe_newsletter", f"beehiiv: would unsubscribe {email} (dry run, nothing changed).",
               changed=False)
        return {"result": "unsubscribed", "dry_run": True}
    base, headers = _beehiiv()
    r = _beehiiv_request("PUT", f"{base}/{sub['id']}", headers, json={"unsubscribe": True})
    r.raise_for_status()
    after = (beehiiv_subscriber(email) or {}).get("status")   # read it back: never report unverified
    if after != "inactive":
        record(ctx, "unsubscribe_newsletter",
               f"beehiiv: asked to unsubscribe {email}, but the status reads {after!r} afterwards. CHECK BY HAND.",
               changed=False, problem=True)
        return {"result": "not_confirmed", "status_after": after,
                "note": "beehiiv accepted the call but the subscriber is not inactive. Tell Igor."}
    record(ctx, "unsubscribe_newsletter", f"beehiiv: {email} unsubscribed from the newsletter (confirmed).",
           changed=True)
    return {"result": "unsubscribed", "status_after": after}


@tool
def tool_cancel_subscription(ctx, email=None, subscription_id=None, **_):
    email = clean_email(email)
    require_in_scope(ctx, email)
    require_approved(ctx, "cancel_subscription", email=email, subscription_id=subscription_id)
    stripe = _stripe(write=not ctx["dry_run"])
    subs = stripe_subscriptions(stripe, email)
    live = [s for s in subs if s["live"]]
    if not live:
        record(ctx, "cancel_subscription", f"Stripe: no live subscription under {email}; nothing changed.",
               changed=False)
        return {"result": "no_live_subscription", "subscriptions": subs,
                "note": "They may pay under another address; ask Igor rather than guessing."}
    if subscription_id:
        chosen = [s for s in live if s["subscription_id"] == subscription_id]
        if not chosen:
            raise Refused(f"{subscription_id} is not a live subscription of {email}")
    elif len(live) > 1:
        return {"result": "several_live_subscriptions", "subscriptions": live,
                "note": "Pass subscription_id only if Igor's instruction says which one; otherwise ask him."}
    else:
        chosen = live
    target = chosen[0]
    label = f"{target['product']} ({target['price']})" if target["price"] else target["product"]
    if target["set_to_cancel"]:
        record(ctx, "cancel_subscription",
               f"Stripe: {label} for {email} was already set to cancel; access until "
               f"{target['access_until_text']}. Nothing changed.", changed=False)
        return {"result": "already_set_to_cancel", **target}
    spend(ctx, "cancel_subscription")
    if ctx["dry_run"]:
        record(ctx, "cancel_subscription",
               f"Stripe: would set {label} for {email} to cancel at period end, "
               f"{target['current_period_ends_text']} (dry run, nothing changed).", changed=False)
        return {"result": "cancelled_at_period_end", "dry_run": True, **target,
                "access_until": target["current_period_ends"],
                "access_until_text": target["current_period_ends_text"]}
    updated = describe_subscription(
        _plain(stripe.Subscription.modify(target["subscription_id"], cancel_at_period_end=True)),
        target["product"])
    if not updated["set_to_cancel"]:
        record(ctx, "cancel_subscription",
               f"Stripe: asked to cancel {label} for {email}, but it does not read as cancelling. CHECK BY HAND.",
               changed=False, problem=True)
        return {"result": "not_confirmed", **updated}
    record(ctx, "cancel_subscription",
           f"Stripe: {label} for {email} set to cancel at the end of the billing period; "
           f"no further charges, access until {updated['access_until_text']}.", changed=True)
    return {"result": "cancelled_at_period_end", **updated}


@tool
def tool_refund_payment(ctx, email=None, charge_id=None, amount_cents=None, **_):
    email = clean_email(email)
    require_in_scope(ctx, email)
    try:
        amount = int(amount_cents)
    except (TypeError, ValueError):
        raise Refused("amount_cents must be a whole number of cents") from None
    charge_id = str(charge_id or "").strip()
    require_approved(ctx, "refund_payment", email=email, charge_id=charge_id, amount_cents=amount)
    stripe = _stripe(write=not ctx["dry_run"])
    charge = find_charge(stripe_charges(stripe, email), charge_id)
    if not charge:
        record(ctx, "refund_payment", f"Stripe: payment {charge_id} is not among {email}'s payments; nothing refunded. "
               "CHECK BY HAND.", changed=False, problem=True)
        return {"result": "not_found"}
    label = f"{money(amount, charge['currency'])} of the {charge['amount']} payment of {charge['date_text']}"
    if amount <= 0 or amount > charge["refundable_cents"]:
        record(ctx, "refund_payment", f"Stripe: could not refund {label} for {email}: only "
               f"{money(charge['refundable_cents'], charge['currency'])} is refundable now. Nothing refunded.",
               changed=False, problem=True)
        return {"result": "not_refundable", **charge}
    spend(ctx, "refund_payment")
    if ctx["dry_run"]:
        record(ctx, "refund_payment", f"Stripe: would refund {label} to {email} (dry run, nothing changed).",
               changed=False)
        return {"result": "refunded", "dry_run": True}
    refund = _plain(stripe.Refund.create(
        charge=charge_id, amount=amount, reason="requested_by_customer",
        metadata={"source": "task_bot", "task": ctx["task_id"]},
        idempotency_key=f"taskbot-{ctx['task_id']}-{charge_id}-{amount}"))
    if refund.get("status") not in ("succeeded", "pending"):
        record(ctx, "refund_payment", f"Stripe: refund of {label} for {email} came back {refund.get('status')!r}. "
               "CHECK BY HAND.", changed=False, problem=True)
        return {"result": "not_confirmed", "status": refund.get("status")}
    pending = " (pending at the bank)" if refund.get("status") == "pending" else ""
    record(ctx, "refund_payment", f"Stripe: refunded {label} to {email}{pending}; it reaches their card in "
           "5 to 10 business days.", changed=True)
    return {"result": "refunded", "status": refund.get("status"), "refund_id": refund.get("id")}


@tool
def tool_lookup_payments(ctx, email=None, **_):
    email = clean_email(email)
    require_in_scope(ctx, email)
    spend(ctx, "lookup_payments")
    return {"email": email, "payments": stripe_charges(_stripe(), email)}


def check_change(ctx: dict, change: dict) -> dict:
    """One proposed change, checked against live data and described for Igor. Returns the stored
    form ({kind, <keys>, text}); raises Invalid when it would do nothing or cannot be done."""
    if not isinstance(change, dict):
        raise Invalid("each change must be an object")
    kind = str(change.get("action") or change.get("kind") or "").strip()
    if kind not in GATED:
        raise Invalid(f"unknown action {kind!r}; use one of {', '.join(GATED)} (drafts go in `drafts`)")
    email = clean_email(change.get("email"))
    require_in_scope(ctx, email)
    if kind == "unsubscribe_newsletter":
        sub = beehiiv_subscriber(email)
        if not sub:
            raise Invalid(f"no beehiiv subscriber has the address {email}")
        if sub.get("status") == "inactive":
            raise Invalid(f"{email} is already unsubscribed")
        return {"kind": kind, "email": email,
                "text": f"Unsubscribe {email} from the Clearer Thinking newsletter (beehiiv)."}
    if kind == "cancel_subscription":
        live = [s for s in stripe_subscriptions(_stripe(), email) if s["live"]]
        sid = str(change.get("subscription_id") or "").strip()
        if not sid and len(live) == 1:
            sid = live[0]["subscription_id"]
        target = next((s for s in live if s["subscription_id"] == sid), None)
        if not target:
            raise Invalid(f"no live subscription {sid or ''} for {email}; live ones: "
                          f"{[s['subscription_id'] for s in live] or 'none'}")
        if target["set_to_cancel"]:
            raise Invalid(f"that subscription is already set to cancel, access until {target['access_until_text']}")
        label = f"{target['product']} ({target['price']})" if target["price"] else target["product"]
        return {"kind": kind, "email": email, "subscription_id": sid,
                "text": f"Set {label} for {email} to cancel at the end of the billing period, "
                        f"{target['current_period_ends_text']}: no further charges, access until then."}
    charges = stripe_charges(_stripe(), email)
    charge = find_charge(charges, str(change.get("charge_id") or "").strip())
    if not charge:
        raise Invalid(f"that charge_id is not one of {email}'s payments; run lookup_payments")
    amount = change.get("amount_cents")
    amount = charge["refundable_cents"] if amount in (None, "") else int(amount)
    if amount <= 0 or amount > charge["refundable_cents"]:
        raise Invalid(f"refundable on that payment: {charge['refundable_cents']} cents")
    whole = " (the full amount)" if amount == charge["amount_cents"] else ""
    what = f" for {charge['description']}" if charge["description"] else ""
    return {"kind": kind, "email": email, "charge_id": charge["charge_id"], "amount_cents": amount,
            "text": f"Refund {money(amount, charge['currency'])}{whole} of the {charge['amount']} payment of "
                    f"{charge['date_text']}{what} to {email}."}


@tool
def tool_propose_changes(ctx, changes=None, drafts=None, **_):
    if ctx.get("mode") != PLAN:
        raise Refused("this run carries out a plan Igor already approved; it cannot propose new changes")
    if not isinstance(changes, list) or not changes:
        raise Invalid("changes must be a non-empty list")
    counts: dict[str, int] = {}
    plan = []
    for change in changes:
        checked = check_change(ctx, change)
        counts[checked["kind"]] = counts.get(checked["kind"], 0) + 1
        if counts[checked["kind"]] > BUDGET[checked["kind"]]:
            raise Refused(f"at most {BUDGET[checked['kind']]} {checked['kind']} changes per task")
        if any(change_key(p["kind"], p) == change_key(checked["kind"], checked) for p in plan):
            continue
        plan.append(checked)
    planned_drafts = []
    for d in drafts or []:
        to = clean_email((d or {}).get("to"))
        recipient_kind(ctx, to)
        planned_drafts.append({"to": to, "purpose": clean_copy((d or {}).get("purpose") or "")[:300]})
    ctx["plan"], ctx["drafts_plan"] = plan, planned_drafts
    return {"saved": True, "plan": [p["text"] for p in plan],
            "note": "Nothing has changed. Igor gets this list and approves it by replying yes."}


def sender_for(ctx: dict, to: str) -> str:
    """Which of Igor's addresses a draft goes out from: the contact's own setting, else the
    address the person originally wrote to (when it is one of his), else the default."""
    contact = find_contact(ctx, to)
    if contact and norm(contact.get("send_from")) in ctx["own_addresses"]:
        return norm(contact["send_from"])
    written_to = norm((ctx["reply_targets"].get(to) or {}).get("written_to"))
    if written_to in ctx["own_addresses"]:
        return written_to
    return ctx.get("default_from") or (ctx["own_addresses"][0] if ctx["own_addresses"] else "")


def build_draft(ctx: dict, to: str, subject: str, body: str):
    """(MIME message, thread id or None). A draft to someone whose email sits in the task's own
    Gmail thread is written as a reply inside that conversation. Pure."""
    target = ctx["reply_targets"].get(to) or {}
    if target.get("subject"):
        base = re.sub(r"^\s*((re|fwd?|fw)\s*:\s*)+", "", target["subject"], flags=re.I).strip()
        subject = f"Re: {base}"
    msg = MIMEText(clean_copy(body).strip() + "\n", "plain", "utf-8")
    msg["To"] = to
    sender = sender_for(ctx, to)
    msg["From"] = formataddr((ctx.get("from_name") or "", sender)) if sender else ""
    msg["Subject"] = clean_copy(subject).strip()
    if target.get("message_id"):
        msg["In-Reply-To"] = target["message_id"]
        msg["References"] = f"{target.get('references', '')} {target['message_id']}".strip()
    return msg, (target.get("thread_id") or None)


@tool
def tool_draft_email(ctx, to=None, subject=None, body=None, **_):
    to = clean_email(to)
    kind = recipient_kind(ctx, to)
    if not str(subject or "").strip() or not str(body or "").strip():
        raise Refused("a draft needs both a subject and a body")
    spend(ctx, "draft_email")
    msg, thread_id = build_draft(ctx, to, str(subject), str(body))
    line = f'to {to}, "{msg["Subject"]}"'
    if ctx["dry_run"]:
        record(ctx, "draft_email", f"Draft (dry run, not created): {line}.", changed=False,
               preview=msg.get_payload(decode=True).decode("utf-8"))
        return {"result": "drafted", "dry_run": True, "from": msg["From"], "subject": msg["Subject"]}
    import advisor_inbox

    message = {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}
    if thread_id:
        message["threadId"] = thread_id
    draft = advisor_inbox.gmail_service().users().drafts().create(
        userId="me", body={"message": message}).execute()
    record(ctx, "draft_email", f"Email drafted in Gmail: {line}.", changed=True,
           draft={"draft_id": draft["id"], "thread_id": (draft.get("message") or {}).get("threadId"),
                  "to": to, "kind": kind, "subject": msg["Subject"], "created_ms": int(time.time() * 1000)})
    return {"result": "drafted", "from": msg["From"], "subject": msg["Subject"],
            "in_original_conversation": bool(thread_id)}


@tool
def tool_finish(ctx, status=None, about=None, summary=None, understood=None, **_):
    status = str(status or "").strip().lower()
    if status not in OUTCOMES:
        raise Refused(f"status must be one of {', '.join(OUTCOMES)}")
    ctx["outcome"] = {"status": status, "about": clean_copy(about or "")[:200],
                      "summary": clean_copy(summary or "")[:600],
                      "understood": clean_copy(understood or "")[:800]}
    return {"saved": True}


TOOL_FNS = {
    "lookup_person": tool_lookup_person,
    "lookup_payments": tool_lookup_payments,
    "propose_changes": tool_propose_changes,
    "draft_email": tool_draft_email,
    "finish": tool_finish,
    # The change tools. Not in TOOLS (the model is never told about them): task_bot.py calls them
    # itself with the approved arguments, and require_approved refuses anything else.
    "unsubscribe_newsletter": tool_unsubscribe_newsletter,
    "cancel_subscription": tool_cancel_subscription,
    "refund_payment": tool_refund_payment,
}

_EMAIL = {"type": "string", "description": "One email address. It must appear in Igor's email."}
TOOLS = [
    {
        "name": "lookup_person",
        "description": "Read-only. What exists for a person: their newsletter (beehiiv) status and their "
                       "Stripe subscriptions (product, price, status, when the current billing period ends, "
                       "whether it is already set to cancel).",
        "input_schema": {"type": "object", "properties": {"email": _EMAIL}},
    },
    {
        "name": "lookup_payments",
        "description": "Read-only. A person's Stripe payments, newest first: charge_id, date, amount, how much "
                       "was already refunded and how much can still be refunded (refundable_cents), description. "
                       "Includes one-off purchases (PDF, Cognitive Assessment) made without an account.",
        "input_schema": {"type": "object", "properties": {"email": _EMAIL}},
    },
    {
        "name": "propose_changes",
        "description": "The ONLY way to get anything changed. Lists the changes you would make; each is checked "
                       "against live data (an invalid one comes back as \"invalid\" with the reason: fix it and "
                       "call again, the last call wins). Nothing changes now: Igor receives the list and the "
                       "changes are made only after he replies yes. Actions: unsubscribe_newsletter {email}; "
                       "cancel_subscription {email, subscription_id} (always at the END of the billing period); "
                       "refund_payment {email, charge_id, amount_cents} (amount_cents optional = everything still "
                       "refundable on that payment).",
        "input_schema": {"type": "object", "properties": {
            "changes": {"type": "array", "description": "List of {\"action\": ..., \"email\": ..., ...}."},
            "drafts": {"type": "array", "description": "Optional. Emails you will draft once the changes are "
                       "made, as [{\"to\": email, \"purpose\": \"what it will say, one line\"}]."}}},
    },
    {
        "name": "draft_email",
        "description": "Leave an email as a DRAFT in Igor's Gmail for him to review and send; nothing is "
                       "sent. Allowed recipients: a person named in Igor's email, one of his saved contacts, "
                       "or Igor. A draft to the person who wrote the forwarded email is placed as a reply in "
                       "that conversation and keeps its subject.",
        "input_schema": {"type": "object", "properties": {
            "to": {"type": "string", "description": "One recipient email address."},
            "subject": {"type": "string", "description": "Subject line."},
            "body": {"type": "string", "description": "Plain-text body, ready to send, signed as Igor."}}},
    },
    {
        "name": "finish",
        "description": "Call once, last, before writing your report. Records the outcome for the task log.",
        "input_schema": {"type": "object", "properties": {
            "status": {"type": "string", "description": "done = finished (a question answered, drafts written, "
                       "or changes proposed for Igor's yes); needs_you = Igor must decide or supply something "
                       "first; cannot_do = the request is outside what these tools can do."},
            "understood": {"type": "string", "description": "What you understood Igor is asking, in one or two "
                           "plain sentences addressed to him (\"You want me to ...\"). He reads this first to "
                           "check you got it right."},
            "about": {"type": "string", "description": "Who the task concerns: name and email, e.g. "
                      "'Jane Doe <jane@example.com>'. Empty for a question about CT."},
            "summary": {"type": "string", "description": "One sentence for the log: what was done or what is "
                        "blocking."}}},
    },
]
