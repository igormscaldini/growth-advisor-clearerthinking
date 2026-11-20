"use client";

// The dashboard's Tasks tab: the task log (everything Igor emails to his +claude address) inside
// the public dashboard. The data is private, so it is fetched from /api/tasks only after the same
// password as the /tasks page; until then the tab shows the password form and nothing else.

import { useCallback, useEffect, useState } from "react";
import type { Task } from "@/lib/tasks";
import { TasksView } from "./tasks-view";

type Loaded = { tasks: Task[]; statuses: string[]; loadedIso: string; error: string };
type State = { kind: "loading" } | { kind: "login"; configured: boolean; wrong: boolean } | { kind: "ready"; data: Loaded };

export function TasksTab() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (wrong = false) => {
    try {
      const res = await fetch("/api/tasks", { cache: "no-store" });
      if (res.status === 401) {
        const body = await res.json();
        setState({ kind: "login", configured: Boolean(body.configured), wrong });
        return;
      }
      setState({ kind: "ready", data: await res.json() });
    } catch {
      setState({ kind: "ready", data: { tasks: [], statuses: [], loadedIso: new Date().toISOString(),
        error: "The task log could not be reached. Check your connection and press Refresh." } });
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the first fetch on mount
    load();
  }, [load]);

  async function post(fields: Record<string, string>) {
    setBusy(true);
    const form = new FormData();
    for (const [k, v] of Object.entries(fields)) form.set(k, v);
    form.set("json", "1");
    try {
      const res = await fetch("/api/tasks-login", { method: "POST", body: form });
      const body = await res.json().catch(() => ({ ok: false }));
      await load(!fields.logout && !body.ok);
    } finally {
      setBusy(false);
    }
  }

  if (state.kind === "loading") {
    return <p className="text-sm text-zinc-500">Loading the task log…</p>;
  }
  if (state.kind === "login") {
    return (
      <div className="mx-auto w-full max-w-sm py-6">
        <h2 className="text-lg font-semibold">Claude tasks</h2>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Private: the log names customers. Enter the task-log password to see it.
        </p>
        {state.configured ? (
          <form
            className="mt-5 flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              post({ password: String(new FormData(e.currentTarget).get("password") ?? "") });
            }}
          >
            <label className="text-sm font-medium" htmlFor="tasks-password">Password</label>
            <input id="tasks-password" name="password" type="password" autoComplete="current-password" required
              className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-base dark:border-zinc-700 dark:bg-zinc-900" />
            {state.wrong && <p role="alert" className="text-sm text-red-700 dark:text-red-400">That password is not right.</p>}
            <button type="submit" disabled={busy}
              className="rounded-lg bg-zinc-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900">
              {busy ? "Checking…" : "Open"}
            </button>
          </form>
        ) : (
          <p role="alert" className="mt-5 text-sm text-red-700 dark:text-red-400">
            Not set up yet: the TASKS_PAGE_PASSWORD variable is missing in Vercel (run bash bots/set_task_bot_secrets.sh page).
          </p>
        )}
      </div>
    );
  }
  const { data } = state;
  return (
    <TasksView tasks={data.tasks} statuses={data.statuses} error={data.error} loadedIso={data.loadedIso}
      embedded onRefresh={() => load()} onSignOut={() => post({ logout: "1" })} />
  );
}
