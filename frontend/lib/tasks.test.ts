import { test } from "node:test";
import assert from "node:assert/strict";
import {
  countByStatus,
  passwordOk,
  rowsToTasks,
  safeThreadUrl,
  sessionOk,
  sessionValue,
  statusesPresent,
  utcToIso,
} from "./tasks.ts";

// The header as task_log.py writes it (COLUMNS).
const HEADER = ["Task", "Received (UTC)", "Status", "Instruction", "About", "Actions", "Summary", "Drafts",
  "Updated (UTC)", "Thread", "Message ID", "Draft data"];
const GMAIL = "https://mail.google.com/mail/?authuser=x@example.com#all/abc";

test("utcToIso converts the sheet's UTC stamp and rejects anything else", () => {
  assert.equal(utcToIso("2026-11-18 18:59:29"), "2026-11-18T18:59:29Z");
  assert.equal(utcToIso(" 2026-11-18T18:59:29 "), "2026-11-18T18:59:29Z");
  assert.equal(utcToIso("yesterday"), "");
  assert.equal(utcToIso(""), "");
});

test("safeThreadUrl only lets a Gmail link through", () => {
  assert.equal(safeThreadUrl(GMAIL), GMAIL);
  assert.equal(safeThreadUrl("javascript:alert(1)"), "");
  assert.equal(safeThreadUrl("https://evil.example/mail.google.com/"), "");
  assert.equal(safeThreadUrl(""), "");
});

test("rowsToTasks maps cells by header name, newest first, and drops blank rows", () => {
  const values = [
    HEADER,
    ["1", "2026-11-18 10:00:00", "Done", "remove them", "Jane <jane@example.com>",
      "beehiiv: jane@example.com unsubscribed (confirmed).", "Unsubscribed.", "", "2026-11-18 10:02:00", GMAIL, "m1", ""],
    [],
    ["2", "2026-11-18 12:00:00", "Drafts waiting", "cancel and tell Angel", "Bob <bob@example.com>",
      "Stripe: set to cancel.\nDraft waiting in Gmail: to bob@example.com.\n", "Cancelled.", "2 waiting",
      "2026-11-18 12:03:00", "javascript:alert(1)", "m2", "[]"],
    ["3", "2026-11-18 11:00:00", "", "short row"],            // no Message ID: not a task
  ];
  const tasks = rowsToTasks(values);
  assert.deepEqual(tasks.map((t) => t.id), ["m2", "m1"]);
  assert.deepEqual(tasks[0].actions, ["Stripe: set to cancel.", "Draft waiting in Gmail: to bob@example.com."]);
  assert.equal(tasks[0].threadUrl, "");                       // not a Gmail link: never rendered as one
  assert.equal(tasks[0].drafts, "2 waiting");
  assert.equal(tasks[1].receivedIso, "2026-11-18T10:00:00Z");
  assert.equal(tasks[1].threadUrl, GMAIL);
  assert.deepEqual(rowsToTasks([]), []);
  assert.deepEqual(rowsToTasks([HEADER]), []);
});

test("rowsToTasks follows the header when the sheet's columns are reordered", () => {
  const values = [["Message ID", "Status", "Task", "Instruction"], ["m9", "Needs you", "9", "which one?"]];
  const [t] = rowsToTasks(values);
  assert.equal(t.id, "m9");
  assert.equal(t.status, "Needs you");
  assert.equal(t.number, "9");
  assert.equal(t.instruction, "which one?");
  assert.equal(t.about, "");
});

test("countByStatus and statusesPresent order what needs Igor first", () => {
  const tasks = rowsToTasks([
    ["Message ID", "Status"], ["a", "Done"], ["b", "Needs you"], ["c", "Done"], ["d", "Paused"], ["e", "Failed"],
  ]);
  assert.deepEqual(countByStatus(tasks), { Done: 2, "Needs you": 1, Paused: 1, Failed: 1 });
  assert.deepEqual(statusesPresent(tasks), ["Needs you", "Failed", "Done", "Paused"]);
});

test("the password gate: right password only, and a cookie that cannot be forged", () => {
  assert.equal(passwordOk("correct horse", "correct horse"), true);
  assert.equal(passwordOk("correct hors", "correct horse"), false);
  assert.equal(passwordOk("", "correct horse"), false);
  assert.equal(passwordOk("anything", undefined), false);      // page not configured: nobody gets in
  assert.equal(passwordOk("", ""), false);

  const cookie = sessionValue("correct horse");
  assert.match(cookie, /^[0-9a-f]{64}$/);
  assert.equal(sessionOk(cookie, "correct horse"), true);
  assert.equal(sessionOk(cookie, "new password"), false);      // changing the password signs everyone out
  assert.equal(sessionOk("correct horse", "correct horse"), false);   // the password itself is not a session
  assert.equal(sessionOk(undefined, "correct horse"), false);
  assert.equal(sessionOk(cookie, undefined), false);
});
