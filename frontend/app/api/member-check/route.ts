// Is this reader a current Clearer Thinking Plus member? Answers {"member": 1} when the address
// has an active or past_due subscription in Stripe, {"member": 0} otherwise.
//
//   GET  /api/member-check?h=<md5 of the email>   newsletter links: beehiiv's {{subscriber_email_hash}}
//   GET  /api/member-check?e=<email>              manual checks (a "+" survives as a space; repaired)
//   POST /api/member-check  {"e": "<email>"}      the pitch page's "Already a member?" form (JSON or
//                                                 form body, so the address needs no URL-encoding)
//
// Called by GuidedTrack program 38912 ("Members-Only Content") through an external service with
// HTTP basic auth: a match sends the reader straight to the full version of a paywalled article
// instead of the pitch page. The typed-email path means anyone who knows a member's address can
// open the article; accepted (Igor, 2026-10-15) because the content is a newsletter section, not
// account data, and basic auth keeps the route from being probed directly. The program keeps a
// static hash list as a fallback for when this endpoint fails (see members_only_programs.py).
//
// Vercel env (production): STRIPE_SECRET_KEY (a restricted key that can read customers and
// subscriptions is enough), MEMBER_CHECK_USER, MEMBER_CHECK_PASSWORD (what GuidedTrack sends).
// The subscriber list is cached in memory for a minute per instance, so a new member is
// recognised within about a minute of paying.

import { basicAuthOk } from "@/lib/workshop-signup";
import {
  emailFromBodyText,
  emailHash,
  hashesFromSubscriptions,
  makeCache,
  normalizeEmail,
  normalizeHash,
  type StripeSubscription,
} from "@/lib/member-check";

export const dynamic = "force-dynamic";

const cache = makeCache<Set<string>>(60_000);

async function stripeSubscriptions(status: string): Promise<StripeSubscription[]> {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) throw new Error("STRIPE_SECRET_KEY is not set");
  const out: StripeSubscription[] = [];
  let startingAfter: string | undefined;
  do {
    const params = new URLSearchParams({ status, limit: "100", "expand[]": "data.customer" });
    if (startingAfter) params.set("starting_after", startingAfter);
    const res = await fetch(`https://api.stripe.com/v1/subscriptions?${params}`, {
      headers: { Authorization: `Bearer ${key}` },
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`stripe subscriptions ${status}: ${res.status} ${(await res.text()).slice(0, 200)}`);
    const page = (await res.json()) as { data: (StripeSubscription & { id: string })[]; has_more: boolean };
    out.push(...page.data);
    startingAfter = page.has_more && page.data.length ? page.data[page.data.length - 1].id : undefined;
  } while (startingAfter);
  return out;
}

async function memberHashes(): Promise<Set<string>> {
  const subs = [...(await stripeSubscriptions("active")), ...(await stripeSubscriptions("past_due"))];
  return hashesFromSubscriptions(subs);
}

function unauthorized() {
  return new Response("Unauthorized", { status: 401, headers: { "WWW-Authenticate": 'Basic realm="member-check"' } });
}

/** The verdict for one hash; `problem` is the 400 message when the input was not usable. */
async function verdict(hash: string | null, problem: string) {
  if (!hash) return Response.json({ member: 0, error: problem }, { status: 400 });
  try {
    const hashes = await cache.get(memberHashes);
    return Response.json({ member: hashes.has(hash) ? 1 : 0 });
  } catch (err) {
    console.error("member-check", err);
    return Response.json({ member: 0, error: "stripe unavailable" }, { status: 502 });
  }
}

const hashOfEmail = (input: string | null) => {
  const email = normalizeEmail(input);
  return email ? emailHash(email) : null;
};

export async function GET(request: Request) {
  if (!basicAuthOk(request.headers.get("authorization"), process.env.MEMBER_CHECK_USER, process.env.MEMBER_CHECK_PASSWORD)) {
    return unauthorized();
  }
  const params = new URL(request.url).searchParams;
  if (params.has("e")) return verdict(hashOfEmail(params.get("e")), "e must be an email address");
  return verdict(normalizeHash(params.get("h")), "h must be a 32-character MD5");
}

export async function POST(request: Request) {
  if (!basicAuthOk(request.headers.get("authorization"), process.env.MEMBER_CHECK_USER, process.env.MEMBER_CHECK_PASSWORD)) {
    return unauthorized();
  }
  return verdict(hashOfEmail(emailFromBodyText(await request.text())), "e must be an email address");
}
