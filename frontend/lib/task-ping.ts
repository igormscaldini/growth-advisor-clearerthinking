// Pure helpers for /api/task-bot-ping, the every-minute check that starts the task bot
// (task_bot.py, workflow task-bot.yml) as soon as Igor emails it. Kept free of Next.js imports
// so `node --test` can run them.
//
// The route only needs a cheap HINT that there may be work: an empty run costs a minute of free
// CI, and the bot itself decides what is really a task (task_bot.classify).

import { timingSafeEqual } from "node:crypto";

export const TASK_TAG = "claude"; // tasks go to <address>+claude@gmail.com (TASK_TAG in task_bot.py)
export const RETRY_MINUTES = 10; // start again if a task email is still untaken after a finished run
export const DRAFTS_MINUTES = 15; // how often to look whether waiting drafts have been sent
/** Gmail's search form of the label "Claude tasks/Drafts waiting" (LABEL_DRAFTS in task_bot.py). */
export const DRAFTS_QUERY = "label:claude-tasks-drafts-waiting";

const ACTIVE = new Set(["queued", "in_progress", "requested", "waiting", "pending"]);

export function taskAddress(own: string): string {
  const [local, domain] = own.trim().toLowerCase().split("@");
  return `${local}+${TASK_TAG}@${domain}`;
}

/** Task emails the bot has not taken yet: sent by the account itself, to the task address,
 *  without the "Claude tasks" label the bot puts on a task as its first step. */
export function pendingQuery(own: string): string {
  return `in:sent to:${taskAddress(own)} -label:claude-tasks newer_than:7d`;
}

export type LastRun = { status: string; createdMs: number };
export type Decision = { start: boolean; reason: string };

/** Should the workflow be started now? `pendingMs` = when the newest untaken task email was
 *  sent (null when there is none); `lastRun` = the workflow's most recent run of any kind. */
export function decideStart(input: {
  nowMs: number;
  pendingMs: number | null;
  draftsWaiting: boolean;
  lastRun: LastRun | null;
}): Decision {
  const { nowMs, pendingMs, draftsWaiting, lastRun } = input;
  if (lastRun && ACTIVE.has(lastRun.status)) return { start: false, reason: "a run is already going" };
  const minutesSinceRun = lastRun ? (nowMs - lastRun.createdMs) / 60_000 : Infinity;
  if (pendingMs != null) {
    // No run has started since the email arrived: this is news.
    if (!lastRun || lastRun.createdMs < pendingMs) return { start: true, reason: "new task email" };
    // A run started after it and finished without taking it (it failed early). Retry, slowly.
    return minutesSinceRun >= RETRY_MINUTES
      ? { start: true, reason: "task email still untaken, retrying" }
      : { start: false, reason: "waiting before retrying an untaken task email" };
  }
  if (draftsWaiting) {
    return minutesSinceRun >= DRAFTS_MINUTES
      ? { start: true, reason: "checking whether waiting drafts were sent" }
      : { start: false, reason: "drafts were checked recently" };
  }
  return { start: false, reason: "nothing to do" };
}

/** Constant-time check of the `Authorization: Bearer <CRON_SECRET>` header Vercel Cron sends. */
export function bearerOk(header: string | null, secret: string | undefined): boolean {
  if (!secret || !header) return false;
  const given = Buffer.from(header);
  const expected = Buffer.from(`Bearer ${secret}`);
  return given.length === expected.length && timingSafeEqual(given, expected);
}
