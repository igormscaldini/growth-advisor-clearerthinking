// Member check for the members-only newsletter flow: is the MD5 of an email address one of the
// current Clearer Thinking Plus subscribers in Stripe? GuidedTrack program 38912 ("Members-Only
// Content") calls GET /api/member-check?h=<md5> through an external service with HTTP basic auth
// and sends matches straight to the full version of the article. beehiiv puts the hash in the
// newsletter link as {{subscriber_email_hash}}: MD5 of the lowercased address, so the Stripe
// emails are hashed the same way. Pure helpers here; Stripe and env access live in the route.
import { createHash } from "node:crypto";

export const HASH_RE = /^[0-9a-f]{32}$/;
// What the team's entitlement check treats as subscribed (program 1pvomgo: active or past_due).
export const MEMBER_STATUSES = new Set(["active", "past_due"]);

export const emailHash = (email: string): string =>
  createHash("md5").update(email.trim().toLowerCase()).digest("hex");

/** The hash from the query string, lowercased, or null when it is not a 32-hex MD5. */
export function normalizeHash(h: string | null | undefined): string | null {
  const v = (h ?? "").trim().toLowerCase();
  return HASH_RE.test(v) ? v : null;
}

export interface StripeSubscription {
  status?: string;
  // Expanded customer object, or just its id when not expanded; deleted customers have no email.
  customer?: { email?: string | null; deleted?: boolean } | string | null;
}

/** Email hashes of every subscriber with a membership status, from Stripe subscription objects. */
export function hashesFromSubscriptions(subs: StripeSubscription[]): Set<string> {
  const out = new Set<string>();
  for (const s of subs) {
    if (!MEMBER_STATUSES.has(s.status ?? "")) continue;
    const email = typeof s.customer === "object" && s.customer ? s.customer.email : null;
    if (email) out.add(emailHash(email));
  }
  return out;
}

/** Keeps one loaded value for `ttlMs`; a failed load leaves the previous value in place. */
export function makeCache<T>(ttlMs: number) {
  let value: T | undefined;
  let expires = 0;
  return {
    async get(load: () => Promise<T>, now: number = Date.now()): Promise<T> {
      if (value !== undefined && now < expires) return value;
      const fresh = await load();
      value = fresh;
      expires = now + ttlMs;
      return fresh;
    },
    /** For tests and manual refreshes. */
    clear() {
      value = undefined;
      expires = 0;
    },
  };
}
