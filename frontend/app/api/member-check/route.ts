// GET /api/member-check?h=<md5 of an email>: {"member": 1} when that address has a current
// Clearer Thinking Plus subscription in Stripe, {"member": 0} otherwise.
//
// Called by GuidedTrack program 38912 ("Members-Only Content") through an external service with
// HTTP basic auth, so a newsletter reader who already pays is sent straight to the full version
// of a paywalled article instead of the pitch page. The program keeps a static list as a fallback
// for when this endpoint fails (see members_only_programs.py in the repo root).
//
// Vercel env (production): STRIPE_SECRET_KEY (a restricted key that can read customers and
// subscriptions is enough), MEMBER_CHECK_USER, MEMBER_CHECK_PASSWORD (what GuidedTrack sends).
// The subscriber list is cached in memory for a minute per instance, so a new member is
// recognised within about a minute of paying.

import { basicAuthOk } from "@/lib/workshop-signup";
import { hashesFromSubscriptions, makeCache, normalizeHash, type StripeSubscription } from "@/lib/member-check";

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

export async function GET(request: Request) {
  if (!basicAuthOk(request.headers.get("authorization"), process.env.MEMBER_CHECK_USER, process.env.MEMBER_CHECK_PASSWORD)) {
    return new Response("Unauthorized", { status: 401, headers: { "WWW-Authenticate": 'Basic realm="member-check"' } });
  }
  const h = normalizeHash(new URL(request.url).searchParams.get("h"));
  if (!h) return Response.json({ member: 0, error: "h must be a 32-character MD5" }, { status: 400 });
  try {
    const hashes = await cache.get(memberHashes);
    return Response.json({ member: hashes.has(h) ? 1 : 0 });
  } catch (err) {
    console.error("member-check", err);
    return Response.json({ member: 0, error: "stripe unavailable" }, { status: 502 });
  }
}
