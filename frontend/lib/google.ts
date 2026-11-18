// Server-side Google access for the routes that read or write a Google Sheet (workshop
// sign-ups, the task log). Auth is the GOOGLE_TOKEN_JSON env var: the same OAuth blob as the
// GitHub secret, of which only the spreadsheets scope is used here.

let cachedToken: { value: string; expiresAt: number } | null = null;

export async function googleAccessToken(): Promise<string> {
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
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`token refresh failed: ${res.status} ${await res.text()}`);
  const data = await res.json();
  cachedToken = { value: data.access_token, expiresAt: Date.now() + Number(data.expires_in ?? 3600) * 1000 };
  return cachedToken.value;
}

/** One Sheets API call on a spreadsheet; `path` starts with "/values/...". Never cached. */
export async function sheetsFetch(
  spreadsheetId: string | undefined,
  path: string,
  init: RequestInit = {},
): Promise<Record<string, unknown>> {
  if (!spreadsheetId) throw new Error("spreadsheet id is not configured");
  const token = await googleAccessToken();
  const res = await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`sheets ${path}: ${res.status} ${await res.text()}`);
  return res.json();
}

/** The "/values/<tab>!<range>" path segment for a tab and an A1 range. */
export const valuesPath = (tab: string, a1: string) => `/values/${encodeURIComponent(`${tab}!${a1}`)}`;
