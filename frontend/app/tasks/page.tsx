// /tasks: every instruction Igor has emailed to the task bot (task_bot.py) and its status.
//
// Private. The rest of this dashboard is public, but this page shows customer names and
// addresses, so it sits behind a password (TASKS_PAGE_PASSWORD, cookie set by
// /api/tasks-login) and is rendered per request, never cached or indexed. The records are read
// straight from the private Google Sheet that task_log.py writes (TASK_LOG_SHEET_ID), with the
// GOOGLE_TOKEN_JSON blob this project already uses for the workshop sheet.

import type { Metadata } from "next";
import { cookies } from "next/headers";
import { TasksView } from "@/components/tasks-view";
import { sheetsFetch, valuesPath } from "@/lib/google";
import { rowsToTasks, SESSION_COOKIE, sessionOk, statusesPresent, type Task, TASKS_TAB } from "@/lib/tasks";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Claude tasks",
  robots: { index: false, follow: false },
};

function Login({ wrong, configured }: { wrong: boolean; configured: boolean }) {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center px-4">
      <h1 className="text-xl font-semibold">Claude tasks</h1>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Private page. Enter the password to see the task log.</p>
      {configured ? (
        <form method="post" action="/api/tasks-login" className="mt-6 flex flex-col gap-3">
          <label className="text-sm font-medium" htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            autoFocus
            className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-base dark:border-zinc-700 dark:bg-zinc-900"
          />
          {wrong && <p role="alert" className="text-sm text-red-700 dark:text-red-400">That password is not right.</p>}
          <button type="submit" className="rounded-lg bg-zinc-900 px-3 py-2 text-sm font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900">
            Open
          </button>
        </form>
      ) : (
        <p role="alert" className="mt-6 text-sm text-red-700 dark:text-red-400">
          This page is not set up yet: the TASKS_PAGE_PASSWORD variable is missing in Vercel.
        </p>
      )}
    </main>
  );
}

export default async function TasksPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const password = process.env.TASKS_PAGE_PASSWORD;
  const cookie = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!sessionOk(cookie, password)) {
    return <Login wrong={Boolean((await searchParams).e)} configured={Boolean(password)} />;
  }

  let tasks: Task[] = [];
  let error = "";
  try {
    const data = await sheetsFetch(process.env.TASK_LOG_SHEET_ID, valuesPath(TASKS_TAB, "A:Z"));
    tasks = rowsToTasks((data.values as unknown[][] | undefined) ?? []);
  } catch (err) {
    console.error("tasks page", err);
    error = "The task log could not be read just now. The bot itself is not affected; try again in a minute.";
  }
  return <TasksView tasks={tasks} statuses={statusesPresent(tasks)} error={error} loadedIso={new Date().toISOString()} />;
}
