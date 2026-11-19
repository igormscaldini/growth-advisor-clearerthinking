// GET /api/task-bot-ping: starts the task bot within a minute of Igor emailing it.
//
// GitHub fires this repo's scheduled workflows only 5 or 6 times a day, so Vercel Cron calls this
// route every minute instead (frontend/vercel.json). It asks Gmail two cheap questions (is there a
// task email the bot has not taken yet? are drafts from an earlier task still waiting to be
// sent?) and, when there is work, asks GitHub to run .github/workflows/task-bot.yml. It sends
// GitHub nothing but "run the workflow" and returns no email content: only a reason string.
//
// Vercel env (production): CRON_SECRET (Vercel Cron sends it as a Bearer token; without it every
// call is refused), GOOGLE_TOKEN_JSON (the Google OAuth blob, Gmail read access),
// TASK_BOT_GITHUB_TOKEN (fine-grained token, this repository only, Actions: read and write;
// set by bots/set_task_bot_secrets.sh). Until that token exists the route reports work as
// waiting and the bot falls back to GitHub's slow schedule.

import { googleAccessToken } from "@/lib/google";
import { bearerOk, decideStart, DRAFTS_QUERY, pendingQuery } from "@/lib/task-ping";

export const dynamic = "force-dynamic";

const REPO = "igormscaldini/growth-advisor-clearerthinking";
const WORKFLOW = "task-bot.yml";

let ownAddress = ""; // per instance: the Gmail account's address never changes

async function gmail(path: string): Promise<Record<string, unknown>> {
  const res = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/${path}`, {
    headers: { Authorization: `Bearer ${await googleAccessToken()}` },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`gmail ${path.split("?")[0]}: ${res.status}`);
  return res.json();
}

async function firstMatch(query: string): Promise<string | null> {
  const data = await gmail(`messages?maxResults=1&q=${encodeURIComponent(query)}`);
  return ((data.messages as { id: string }[] | undefined) ?? [])[0]?.id ?? null;
}

async function github(token: string, path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "ct-task-bot-ping",
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });
}

export async function GET(request: Request) {
  if (!bearerOk(request.headers.get("authorization"), process.env.CRON_SECRET)) {
    return new Response("Unauthorized", { status: 401 });
  }
  try {
    if (!ownAddress) ownAddress = String((await gmail("profile")).emailAddress ?? "");
    const pendingId = await firstMatch(pendingQuery(ownAddress));
    const pendingMs = pendingId ? Number((await gmail(`messages/${pendingId}?format=minimal`)).internalDate) : null;
    const draftsWaiting = pendingId ? false : Boolean(await firstMatch(DRAFTS_QUERY));
    if (pendingMs == null && !draftsWaiting) return Response.json({ ok: true, started: false, reason: "nothing to do" });

    const token = process.env.TASK_BOT_GITHUB_TOKEN;
    if (!token) {
      return Response.json({ ok: false, started: false, reason: "work is waiting, but TASK_BOT_GITHUB_TOKEN is not set" });
    }
    const runsRes = await github(token, "/runs?per_page=1");
    if (!runsRes.ok) throw new Error(`github runs: ${runsRes.status}`);
    const latest = ((await runsRes.json()).workflow_runs ?? [])[0];
    const lastRun = latest ? { status: String(latest.status), createdMs: Date.parse(latest.created_at) } : null;

    const decision = decideStart({ nowMs: Date.now(), pendingMs, draftsWaiting, lastRun });
    if (!decision.start) return Response.json({ ok: true, started: false, reason: decision.reason });

    const startRes = await github(token, "/dispatches", { method: "POST", body: JSON.stringify({ ref: "main" }) });
    if (startRes.status !== 204) throw new Error(`github dispatch: ${startRes.status}`);
    return Response.json({ ok: true, started: true, reason: decision.reason });
  } catch (err) {
    console.error("task-bot-ping", err instanceof Error ? err.message : err);
    return Response.json({ ok: false, started: false, reason: "check failed, see the function log" }, { status: 502 });
  }
}
