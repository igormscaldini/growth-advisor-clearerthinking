// POST /api/workshop-signup: one sign-up from the GuidedTrack program "Career Change
// Workshop Sign-up" (its *service "Sign-up sheet" posts here with HTTP basic auth).
// Upserts a row in the Google Sheet keyed on the email address.
//
// Vercel env (production): WORKSHOP_SIGNUP_USER, WORKSHOP_SIGNUP_PASSWORD (what GuidedTrack
// sends), WORKSHOP_SHEET_ID, GOOGLE_TOKEN_JSON (the same OAuth blob as the GitHub secret;
// only its spreadsheets scope is used). The Python backfill (workshop_signups_sheet.py) was deleted on 2026-10-02.

import { sheetsFetch, valuesPath } from "@/lib/google";
import { basicAuthOk, findEmailRow, normalizeSignup, parseBody, SHEET_TAB, toRow } from "@/lib/workshop-signup";

const sheets = (path: string, init: RequestInit = {}) => sheetsFetch(process.env.WORKSHOP_SHEET_ID, path, init);
const range = (a1: string) => valuesPath(SHEET_TAB, a1);

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
      await sheets(`${range(`A${rowNumber}:D${rowNumber}`)}?valueInputOption=RAW`, { method: "PUT", body: JSON.stringify({ values: [row] }) });
      return Response.json({ ok: true, action: "updated" });
    }
    await sheets(`${range("A:D")}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`, { method: "POST", body: JSON.stringify({ values: [row] }) });
    return Response.json({ ok: true, action: "appended" });
  } catch (err) {
    console.error("workshop-signup", err);
    return Response.json({ ok: false, error: "sheet write failed" }, { status: 502 });
  }
}
