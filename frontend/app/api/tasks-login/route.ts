// POST /api/tasks-login: the password form of the private task log (the /tasks page and the
// dashboard's Tasks tab).
//   password=<typed>   right: set the session cookie and go to /tasks; wrong: back to /tasks?e=1
//   logout=1           clear the cookie
//   json=1             answer {ok: boolean} instead of redirecting (the Tasks tab posts with fetch)
//
// Vercel env (production): TASKS_PAGE_PASSWORD. The page shows customer names and addresses, so
// with the variable unset nobody gets in.

import { NextResponse } from "next/server";
import { passwordOk, SESSION_COOKIE, SESSION_DAYS, sessionValue } from "@/lib/tasks";

const cookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  // "/" so the cookie also reaches /api/tasks, which the dashboard's Tasks tab reads.
  path: "/",
};

export async function POST(request: Request) {
  const form = await request.formData();
  const json = Boolean(form.get("json"));
  const back = (query = "") =>
    json
      ? NextResponse.json({ ok: !query })
      : NextResponse.redirect(new URL(`/tasks${query}`, request.url), 303);

  if (form.get("logout")) {
    const res = back();
    res.cookies.set(SESSION_COOKIE, "", { ...cookieOptions, maxAge: 0 });
    res.cookies.set(SESSION_COOKIE, "", { ...cookieOptions, path: "/tasks", maxAge: 0 }); // pre-2026-11-20 cookie
    return res;
  }

  const expected = process.env.TASKS_PAGE_PASSWORD;
  if (!passwordOk(String(form.get("password") ?? ""), expected)) {
    await new Promise((resolve) => setTimeout(resolve, 800)); // slows guessing to a crawl
    return back("?e=1");
  }
  const res = back();
  res.cookies.set(SESSION_COOKIE, sessionValue(expected as string), { ...cookieOptions, maxAge: SESSION_DAYS * 86400 });
  return res;
}
