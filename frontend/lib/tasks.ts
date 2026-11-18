// Pure helpers for the private /tasks page (app/tasks/page.tsx): the log of everything Igor has
// emailed to the task bot (task_bot.py). Kept free of Next.js imports so `node --test` can run them.
//
// The records live in a private Google Sheet written by task_log.py. Cells are mapped by the
// header NAMES below (the same strings as COLUMNS in task_log.py), so the sheet's column order
// can change freely; a rename has to be made in both files.

import { createHash, createHmac, timingSafeEqual } from "node:crypto";

export const TASKS_TAB = "Tasks";
export const SESSION_COOKIE = "ct_tasks";
export const SESSION_DAYS = 180;

/** Display order: what needs Igor first, finished work last. */
export const STATUSES = ["Needs you", "Drafts waiting", "Running", "Failed", "Done"] as const;

export type Task = {
  id: string;
  number: string;
  receivedIso: string;
  updatedIso: string;
  status: string;
  instruction: string;
  about: string;
  actions: string[];
  summary: string;
  drafts: string;
  threadUrl: string;
};

function str(v: unknown): string {
  return v == null ? "" : String(v).trim();
}

/** "2026-11-18 18:59:29" (UTC, as task_log.py writes it) -> ISO; "" when it is not a timestamp. */
export function utcToIso(value: string): string {
  const m = /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})$/.exec(value.trim());
  return m ? `${m[1]}T${m[2]}Z` : "";
}

/** Only a Gmail link is ever rendered as a link: the cell is data, not a trusted URL. */
export function safeThreadUrl(value: string): string {
  return value.startsWith("https://mail.google.com/") ? value : "";
}

/** Sheet values (header row first) -> tasks, newest first. Blank rows and rows without an id are dropped. */
export function rowsToTasks(values: unknown[][]): Task[] {
  if (!values.length) return [];
  const header = values[0].map(str);
  const col = (name: string) => header.indexOf(name);
  const cell = (row: unknown[], name: string) => (col(name) >= 0 ? str(row[col(name)]) : "");
  const tasks: Task[] = [];
  for (const row of values.slice(1)) {
    const id = cell(row, "Message ID");
    if (!id) continue;
    tasks.push({
      id,
      number: cell(row, "Task"),
      receivedIso: utcToIso(cell(row, "Received (UTC)")),
      updatedIso: utcToIso(cell(row, "Updated (UTC)")),
      status: cell(row, "Status") || "Running",
      instruction: cell(row, "Instruction"),
      about: cell(row, "About"),
      actions: cell(row, "Actions").split("\n").map((s) => s.trim()).filter(Boolean),
      summary: cell(row, "Summary"),
      drafts: cell(row, "Drafts"),
      threadUrl: safeThreadUrl(cell(row, "Thread")),
    });
  }
  return tasks.sort((a, b) => (b.receivedIso || "").localeCompare(a.receivedIso || "") || Number(b.number) - Number(a.number));
}

export function countByStatus(tasks: Task[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const t of tasks) counts[t.status] = (counts[t.status] ?? 0) + 1;
  return counts;
}

/** Statuses present in the log, in display order (unknown ones last). */
export function statusesPresent(tasks: Task[]): string[] {
  const counts = countByStatus(tasks);
  const known = STATUSES.filter((s) => counts[s]);
  const other = Object.keys(counts).filter((s) => !(STATUSES as readonly string[]).includes(s)).sort();
  return [...known, ...other];
}

// --- the page's password gate ---------------------------------------------------------------
// One shared password (env TASKS_PAGE_PASSWORD). The cookie holds an HMAC of a fixed string keyed
// by the password, so it cannot be forged without the password and changing the password signs
// every device out.

const digest = (s: string) => createHash("sha256").update(s).digest();

/** Constant-time comparison of the typed password with the configured one. */
export function passwordOk(given: string, expected: string | undefined): boolean {
  if (!expected || !given) return false;
  return timingSafeEqual(digest(given), digest(expected));
}

export function sessionValue(password: string): string {
  return createHmac("sha256", password).update("ct-tasks-session-v1").digest("hex");
}

export function sessionOk(cookie: string | undefined, password: string | undefined): boolean {
  if (!cookie || !password) return false;
  return timingSafeEqual(digest(cookie), digest(sessionValue(password)));
}
