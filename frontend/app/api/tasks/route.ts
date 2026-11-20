// GET /api/tasks: the task log as JSON for the dashboard's Tasks tab (components/tasks-tab.tsx).
//   200 {tasks, statuses, loadedIso, error}   signed in (the cookie set by /api/tasks-login)
//   401 {configured}                           not signed in; configured=false when TASKS_PAGE_PASSWORD is unset
//
// Private: the log holds customer names and addresses, so it is never cached. Same source as the
// /tasks page: the Google Sheet task_log.py writes (TASK_LOG_SHEET_ID).

import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { sheetsFetch, valuesPath } from "@/lib/google";
import { rowsToTasks, SESSION_COOKIE, sessionOk, statusesPresent, type Task, TASKS_TAB } from "@/lib/tasks";

export const dynamic = "force-dynamic";

const noStore = { "Cache-Control": "private, no-store" };

export async function GET() {
  const password = process.env.TASKS_PAGE_PASSWORD;
  const cookie = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!sessionOk(cookie, password)) {
    return NextResponse.json({ configured: Boolean(password) }, { status: 401, headers: noStore });
  }
  let tasks: Task[] = [];
  let error = "";
  try {
    const data = await sheetsFetch(process.env.TASK_LOG_SHEET_ID, valuesPath(TASKS_TAB, "A:Z"));
    tasks = rowsToTasks((data.values as unknown[][] | undefined) ?? []);
  } catch (err) {
    console.error("api/tasks", err);
    error = "The task log could not be read just now. The bot itself is not affected; try again in a minute.";
  }
  return NextResponse.json(
    { tasks, statuses: statusesPresent(tasks), loadedIso: new Date().toISOString(), error },
    { headers: noStore },
  );
}
