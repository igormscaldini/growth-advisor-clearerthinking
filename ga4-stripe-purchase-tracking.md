# Track every Stripe sale in GA4 as a `purchase` / transaction

> **CT setup note:** all checkouts are **Stripe-hosted Payment Links / subscription links** (no custom checkout page). That means:
> - **Getting revenue + transactions into GA4 needs NO code** — a Zapier connection (Stripe → GA4) captures every sale. See "Level 1 (no-code)" below.
> - **Channel attribution (Google vs Meta)** does NOT need the server code in section B/C. The only extra step is appending the visitor's GA4 id to the Payment Link as `?client_reference_id=…`. See the **"Payment Links"** subsection under B.
> Sections C's webhook code is an *alternative* to Zapier for teams with a developer; with Payment Links you can do everything through Zapier + the `client_reference_id` trick.

---

## Level 1 — all sales into GA4 (no developer, ~30 min, works with Payment Links)

1. In GA4: Admin → Data Streams → your website stream. Copy the **Measurement ID** (`G-…`) and create a **Measurement Protocol API secret** (same screen). These are the two "keys" Zapier needs.
2. Create a free **Zapier** account.
3. **Zap 1 — one-time sales.** Trigger: **Stripe → "Checkout Session Completed"** (covers Payment Links). Action: **Google Analytics 4 → "Send Measurement Protocol Event"**. Paste the Measurement ID + secret. Map: event name `purchase`; `transaction_id` = the Stripe session/payment ID; `value` = amount **÷ 100** (add a Formatter "divide by 100" step, Stripe is in cents); `currency` = `usd`.
4. **Zap 2 — subscription renewals.** Same as Zap 1 but Trigger: **Stripe → "Invoice Payment Succeeded"**; `transaction_id` = the invoice ID.
5. Turn both on, make a test purchase, confirm in GA4 → Realtime. Revenue shows in Monetization within 24–48h.

This gives you total revenue + transaction counts. It will **not** label sales Google vs Meta until you also do the `client_reference_id` step below.

---


Goal: every Stripe sale fires a GA4 **`purchase`** event with a `transaction_id`, `value`, and `currency`, so it shows up in GA4 Monetization (transactions + revenue) **and** attributes to the acquisition channel (google `upt_pmax` vs meta `upt_meta_ads`, etc.) so you can measure ROAS by channel.

**Architecture (why):** Stripe payments complete server-side, and hosted Checkout/Payment-Link pages mean the buyer often never lands back on your site — so a client-side `purchase` on a thank-you page misses sales. The reliable source of truth is a **Stripe webhook → GA4 Measurement Protocol (MP)** server call. To attribute revenue to a channel, GA4 joins the MP event to the user via `client_id`, so you must capture the GA4 `client_id` at checkout and pass it through Stripe.

---

## A. GA4 setup (Admin — one time)

1. **Identify the right web stream.** Use the same GA4 Data Stream that the tool site (`programs.clearerthinking.org`) uses for gtag, so `client_id`s match. Note its **Measurement ID** (`G-XXXXXXXXXX`), Admin → Data Streams → [stream].
2. **Create a Measurement Protocol API secret.** Same stream → *Measurement Protocol API secrets* → **Create** → copy the secret. (Store it as `GA4_MP_API_SECRET`, and the `G-…` as `GA4_MEASUREMENT_ID`.)
3. **Nothing to "turn on" for ecommerce:** `purchase` is a GA4 *recommended* event, so sending it auto-populates Monetization → Ecommerce purchases (transactions, revenue). Just make sure you always send `currency` + `value` or revenue won't show.
4. **(Optional) Mark `purchase` as a Key event** (Admin → Events) if you want it as a conversion, and import it into Google Ads for bidding.

## B. Capture the GA4 identifiers at checkout (site)

5. On the page where the user starts checkout, read `client_id` (and `session_id`) from gtag and attach them to your "create checkout" request:
   ```html
   <script>
   const GA_ID = 'G-XXXXXXXXXX';
   window.gaIds = {};
   gtag('get', GA_ID, 'client_id',  v => window.gaIds.client_id  = v);
   gtag('get', GA_ID, 'session_id', v => window.gaIds.session_id = v);
   // also grab utm/gclid/fbclid from the URL if you store them
   </script>
   ```
6. **Pass them into Stripe.** When you create the Checkout Session server-side, store them in `metadata` and `client_reference_id`:
   ```python
   session = stripe.checkout.Session.create(
       mode="payment",                       # "subscription" for CT+ / recurring
       line_items=[{"price": PRICE_ID, "quantity": 1}],
       success_url="https://.../thank-you?sid={CHECKOUT_SESSION_ID}",
       cancel_url="https://.../cancelled",
       client_reference_id=ga_client_id,     # GA4 client_id
       metadata={
           "ga_client_id": ga_client_id,
           "ga_session_id": ga_session_id,
           "utm_source": utm_source, "utm_medium": utm_medium, "utm_campaign": utm_campaign,
       },
       # For subscriptions, also copy ga_client_id onto the Customer so renewals can attribute:
       subscription_data={"metadata": {"ga_client_id": ga_client_id}},  # subscription mode only
   )
   ```
### Payment Links (CT's setup) — the simple attribution add-on

You don't need the server code above. Stripe Payment Links accept a `client_reference_id` in the URL, and it flows into the `checkout.session.completed` event (and into Zapier). So the only task is: **wherever the Buy/Subscribe button points to the Stripe link, append the visitor's GA4 id.**

A short snippet on the page/template that shows the link does it:
```html
<script>
const GA_ID = 'G-XXXXXXXXXX';
gtag('get', GA_ID, 'client_id', function (cid) {
  document.querySelectorAll('a[href*="buy.stripe.com"], a[href*="pay.link"]').forEach(function (a) {
    const u = new URL(a.href);
    u.searchParams.set('client_reference_id', cid);   // GA4 visitor id rides along
    a.href = u.toString();
  });
});
</script>
```
Then in **Zapier's** GA4 action, map **`client_id` = the Stripe event's `client_reference_id`** (instead of a placeholder). Now each Payment Link sale attributes to the channel (google `upt_pmax` vs meta `upt_meta_ads`, etc.).

- **Subscriptions:** the first payment carries the `client_reference_id`; to keep *renewals* attributed, have the snippet also live where the subscription link is shown, and (if a developer is available) copy the id onto the Stripe Customer so renewal invoices inherit it. Renewals still count as revenue via Zap 2 regardless — they just may show as unattributed.
- This snippet needs someone who can edit the page/email/tool template where the link appears (a small task, not a full developer project).

## C. Stripe webhook → GA4 Measurement Protocol (server — the core)

7. **Create a webhook** (Stripe Dashboard → Developers → Webhooks) pointing at your endpoint, subscribed to:
   - `checkout.session.completed` — one-time purchases + the first subscription payment
   - `invoice.paid` — subscription **renewals** (each renewal = a new transaction)
   - `charge.refunded` — to send GA4 `refund` events (optional, keeps revenue accurate)
8. **Handle the event, verify the signature, and send the `purchase` to MP:**
   ```python
   import os, stripe, requests
   from flask import Flask, request

   app = Flask(__name__)
   stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
   WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
   MP_URL = ("https://www.google-analytics.com/mp/collect"
             f"?measurement_id={os.environ['GA4_MEASUREMENT_ID']}"
             f"&api_secret={os.environ['GA4_MP_API_SECRET']}")

   def send_ga_purchase(client_id, session_id, transaction_id, value, currency, items, event_name="purchase"):
       # Fallback so revenue is still counted (but unattributed) when we have no client_id:
       client_id = client_id or f"555.{transaction_id}"
       params = {
           "transaction_id": transaction_id,
           "value": round(float(value), 2),
           "currency": (currency or "usd").upper(),
           "items": items or [{"item_name": "CT product", "price": round(float(value), 2), "quantity": 1}],
           "engagement_time_msec": 1,
       }
       if session_id:
           params["session_id"] = session_id          # helps session-level attribution
       body = {"client_id": client_id, "events": [{"name": event_name, "params": params}]}
       requests.post(MP_URL, json=body, timeout=5)

   def line_items(stripe_session):
       out = []
       li = stripe.checkout.Session.list_line_items(stripe_session["id"], limit=100)
       for it in li.data:
           out.append({
               "item_name": it.description,
               "price": (it.amount_total or 0) / 100,
               "quantity": it.quantity or 1,
           })
       return out

   @app.post("/stripe/webhook")
   def webhook():
       event = stripe.Webhook.construct_event(
           request.data, request.headers["Stripe-Signature"], WEBHOOK_SECRET)
       t = event["type"]

       if t == "checkout.session.completed":
           s = event["data"]["object"]
           send_ga_purchase(
               client_id=s.get("client_reference_id") or (s.get("metadata") or {}).get("ga_client_id"),
               session_id=(s.get("metadata") or {}).get("ga_session_id"),
               transaction_id=s["id"],                      # unique & stable
               value=(s.get("amount_total") or 0) / 100,    # Stripe is in CENTS
               currency=s.get("currency"),
               items=line_items(s),
           )

       elif t == "invoice.paid":                            # subscription renewals
           inv = event["data"]["object"]
           cust = stripe.Customer.retrieve(inv["customer"])
           send_ga_purchase(
               client_id=(cust.get("metadata") or {}).get("ga_client_id"),
               session_id=None,
               transaction_id=inv["id"],                    # each invoice is unique
               value=(inv.get("amount_paid") or 0) / 100,
               currency=inv.get("currency"),
               items=[{"item_name": "Clearer Thinking Plus", "price": (inv.get("amount_paid") or 0)/100, "quantity": 1}],
           )

       elif t == "charge.refunded":
           ch = event["data"]["object"]
           send_ga_purchase(
               client_id=(ch.get("metadata") or {}).get("ga_client_id"),
               session_id=None,
               transaction_id=ch.get("payment_intent") or ch["id"],
               value=(ch.get("amount_refunded") or 0) / 100,
               currency=ch.get("currency"),
               items=None,
               event_name="refund",
           )

       return "", 200
   ```

## D. (Optional) Client-side redundancy + dedup

9. You *can* also fire `purchase` on the thank-you page with gtag — but use the **same `transaction_id`** as the server, and GA4 will dedupe. The server-side MP call is the source of truth; only add client-side if you want faster Realtime confirmation.

## E. Test & verify

10. **Stripe test mode:** `stripe listen --forward-to localhost:PORT/stripe/webhook`, then `stripe trigger checkout.session.completed`.
11. **Validate the MP payload:** POST the same body to `https://www.google-analytics.com/debug/mp/collect?...` — it returns validation errors.
12. **See it live:** GA4 **DebugView** (add `debug_mode: true` while testing) and **Realtime**. Transactions/revenue appear in **Monetization → Ecommerce purchases** within 24–48h.
13. **Reconcile:** compare GA4 transactions + revenue for one day against the Stripe dashboard; they should match closely.

---

## Gotchas / rules
- **Cents → dollars:** every Stripe amount is in the smallest unit; divide by 100.
- **`currency`** must be lowercase ISO on the Stripe side; send it (upper or lower both accepted by GA4). Without value+currency, revenue won't populate.
- **`transaction_id` must be unique and stable** (Checkout Session id, Invoice id). Reusing an id double-counts; a stable id lets client+server dedupe.
- **Attribution needs `client_id`.** No client_id → the sale still counts toward total revenue (via the fallback id) but won't attribute to google/meta. That's why B is essential.
- **Subscriptions:** decide whether each renewal counts as a transaction (recommended for true revenue). Copy `ga_client_id` onto the Stripe **Customer** so renewals stay attributed.
- **Measurement Protocol bypasses Consent Mode** — make sure server-side sends comply with your consent/privacy policy.
- **Use the site's own stream** `G-…` for MP; a mismatched stream means client_ids won't join and attribution breaks.

## Env vars to set on the webhook server
```
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
GA4_MEASUREMENT_ID=G-XXXXXXXXXX        # the site's web stream
GA4_MP_API_SECRET=...                  # from step A2
```
