import { test } from "node:test";
import assert from "node:assert/strict";
import { bearerOk, decideStart, DRAFTS_MINUTES, pendingQuery, RETRY_MINUTES, taskAddress } from "./task-ping.ts";

const MIN = 60_000;
const NOW = 1_000 * MIN; // an arbitrary "now", in ms
const run = (status: string, minutesAgo: number) => ({ status, createdMs: NOW - minutesAgo * MIN });
const decide = (pendingMinutesAgo: number | null, draftsWaiting: boolean, lastRun: ReturnType<typeof run> | null) =>
  decideStart({ nowMs: NOW, pendingMs: pendingMinutesAgo == null ? null : NOW - pendingMinutesAgo * MIN, draftsWaiting, lastRun });

test("taskAddress and pendingQuery follow the +claude convention", () => {
  assert.equal(taskAddress(" Someone@Gmail.com "), "someone+claude@gmail.com");
  assert.equal(pendingQuery("someone@gmail.com"), "in:sent to:someone+claude@gmail.com -label:claude-tasks newer_than:7d");
});

test("nothing waiting: never start", () => {
  assert.deepEqual(decide(null, false, null), { start: false, reason: "nothing to do" });
  assert.equal(decide(null, false, run("completed", 500)).start, false);
});

test("a new task email starts a run at once, unless one is already going", () => {
  assert.equal(decide(0.5, false, null).start, true);                       // first task ever
  assert.equal(decide(0.5, false, run("completed", 240)).start, true);      // last run was hours ago
  assert.equal(decide(0.5, false, run("completed", 1)).start, true);        // a run ended a minute ago, the email is newer
  for (const status of ["queued", "in_progress", "requested", "waiting", "pending"]) {
    assert.deepEqual(decide(0.5, false, run(status, 0.2)), { start: false, reason: "a run is already going" });
  }
});

test("an email a finished run failed to take is retried only every RETRY_MINUTES", () => {
  // the run started 2 minutes after the email and has finished, yet the email is still untaken
  assert.equal(decide(5, false, run("completed", 3)).start, false);
  assert.equal(decide(RETRY_MINUTES + 3, false, run("completed", RETRY_MINUTES - 0.1)).start, false);
  assert.equal(decide(RETRY_MINUTES + 3, false, run("completed", RETRY_MINUTES)).start, true);
});

test("an email that arrived while a run was going starts a new run once that one ends", () => {
  assert.equal(decide(1, false, run("in_progress", 2)).start, false);
  assert.equal(decide(1, false, run("completed", 2)).start, true);          // that run began before the email
});

test("waiting drafts are re-checked every DRAFTS_MINUTES, and a task email takes priority", () => {
  assert.equal(decide(null, true, run("completed", DRAFTS_MINUTES - 1)).start, false);
  assert.equal(decide(null, true, run("completed", DRAFTS_MINUTES)).start, true);
  assert.equal(decide(null, true, null).start, true);
  assert.equal(decide(null, true, run("in_progress", 30)).start, false);
  assert.equal(decide(0.5, true, run("completed", 1)).reason, "new task email");
});

test("bearerOk accepts only the exact cron secret", () => {
  assert.equal(bearerOk("Bearer s3cret", "s3cret"), true);
  assert.equal(bearerOk("Bearer s3cre", "s3cret"), false);
  assert.equal(bearerOk("bearer s3cret", "s3cret"), false);
  assert.equal(bearerOk("s3cret", "s3cret"), false);
  assert.equal(bearerOk(null, "s3cret"), false);
  assert.equal(bearerOk("Bearer ", ""), false);                              // secret not configured: nobody gets in
  assert.equal(bearerOk("Bearer undefined", undefined), false);
});
