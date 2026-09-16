// POST /api/workshop-signup: one sign-up from the GuidedTrack program "Career Change
// Workshop Sign-up" (its *service "Sign-up sheet" posts here with HTTP basic auth).
// Upserts a row in the Google Sheet keyed on the email address.
//
// Vercel env (production): WORKSHOP_SIGNUP_USER, WORKSHOP_SIGNUP_PASSWORD (what GuidedTrack
// sends), WORKSHOP_SHEET_ID, GOOGLE_TOKEN_JSON (the same OAuth blob as the GitHub secret;
// only its spreadsheets scope is used). The backfill / safety net is workshop_signups_sheet.py.

import { basicAuthOk, findEmailRow, normalizeSignup, parseBody, SHEET_TAB, toRow } from "@/lib/workshop-signup";

let cachedToken: { value: string; expiresAt: number } | null = null;

async function accessToken(): Promise<string> {
  if (cachedToken && cachedToken.expiresAt > Date.now() + 60_000) return cachedToken.value;
  const blob = JSON.parse(process.env.GOOGLE_TOKEN_JSON ?? "{}");
  const res = await fetch(blob.token_uri ?? "https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: blob.client_id,
      client_secret: blob.client_secret,
      refresh_token: blob.refresh_token,
      grant_type: "refresh_token",
    }),
  });
  if (!res.ok) throw new Error(`token refresh failed: ${res.status} ${await res.text()}`);
  const data = await res.json();
  cachedToken = { value: data.access_token, expiresAt: Date.now() + Number(data.expires_in ?? 3600) * 1000 };
  return cachedToken.value;
}

async function sheets(path: string, init: RequestInit = {}): Promise<Record<string, unknown>> {
  const token = await accessToken();
  const res = await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${process.env.WORKSHOP_SHEET_ID}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`sheets ${path}: ${res.status} ${await res.text()}`);
  return res.json();
}

const range = (a1: string) => `/values/${encodeURIComponent(`${SHEET_TAB}!${a1}`)}`;

export async function POST(request: Request) {
  if (!basicAuthOk(request.headers.get("authorization"), process.env.WORKSHOP_SIGNUP_USER, process.env.WORKSHOP_SIGNUP_PASSWORD)) {
    return new Response("Unauthorized", { status: 401, headers: { "WWW-Authenticate": 'Basic realm="workshop-signup"' } });
  }
  const signup = normalizeSignup(parseBody(request.headers.get("content-type"), await request.text()));
  if (!signup) return Response.json({ ok: false, error: "missing email" }, { status: 400 });
  const row = toRow(signup, new Date());
  try {
    const existing = await sheets(range("B:B"));
    const rowNumber = findEmailRow((existing.values as string[][] | undefined) ?? [], signup.email);
    if (rowNumber) {
      await sheets(`${range(`A${rowNumber}:G${rowNumber}`)}?valueInputOption=RAW`, { method: "PUT", body: JSON.stringify({ values: [row] }) });
      return Response.json({ ok: true, action: "updated" });
    }
    await sheets(`${range("A:G")}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`, { method: "POST", body: JSON.stringify({ values: [row] }) });
    return Response.json({ ok: true, action: "appended" });
  } catch (err) {
    console.error("workshop-signup", err);
    return Response.json({ ok: false, error: "sheet write failed" }, { status: 502 });
  }
}
