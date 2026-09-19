// Pure helpers for the workshop sign-up endpoint (app/api/workshop-signup/route.ts).
// Kept free of Next.js imports so they can be unit-tested with `node --test`.
// Column layout is shared with workshop_signups_sheet.py in the repo root: keep HEADER in step.

import { timingSafeEqual } from "node:crypto";

export const SHEET_TAB = "Sign-ups";
export const HEADER = ["Signed up (UTC)", "Email", "First name", "Question for the session"];

export type Signup = {
  email: string;
  firstName: string;
  question: string;
};

function str(v: unknown): string {
  return v == null ? "" : String(v).trim();
}

/** GuidedTrack may send JSON or a form body; accept both. */
export function parseBody(contentType: string | null, text: string): Record<string, unknown> {
  const trimmed = text.trim();
  const isJson = (contentType ?? "").includes("json") || trimmed.startsWith("{");
  if (!isJson) return Object.fromEntries(new URLSearchParams(trimmed));
  try {
    const parsed = JSON.parse(trimmed);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

/** Normalise the raw payload; null when there is no usable email address. */
export function normalizeSignup(raw: Record<string, unknown>): Signup | null {
  // The trailing dot is dropped for the same reason as in workshop_signups_sheet.py: it is a
  // typo, mail to it bounces, and keeping it would file the person under a second address.
  const email = str(raw.email).toLowerCase().replace(/\.+$/, "");
  if (!email.includes("@")) return null;
  return { email, firstName: str(raw.firstName), question: str(raw.question) };
}

/** Constant-time check of an HTTP Basic Authorization header against the expected pair. */
export function basicAuthOk(header: string | null, user: string | undefined, password: string | undefined): boolean {
  if (!user || !password || !header || !header.startsWith("Basic ")) return false;
  const expected = Buffer.from(`${user}:${password}`);
  const given = Buffer.from(header.slice(6).trim(), "base64");
  return given.length === expected.length && timingSafeEqual(given, expected);
}

/** 1-based sheet row holding this email (column B), skipping the header; 0 when absent. */
export function findEmailRow(columnB: string[][], email: string): number {
  for (let i = 1; i < columnB.length; i++) {
    if ((columnB[i]?.[0] ?? "").trim().toLowerCase() === email) return i + 1;
  }
  return 0;
}

export function toRow(signup: Signup, receivedAt: Date): string[] {
  const utc = receivedAt.toISOString().replace("T", " ").slice(0, 19);
  return [utc, signup.email, signup.firstName, signup.question];
}
