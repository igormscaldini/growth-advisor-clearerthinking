"use client";

// The task log as Igor reads it on his phone: what needs him first, then everything else,
// newest first. Two hosts: the /tasks page (server component, refreshes with router.refresh) and
// the dashboard's Tasks tab (components/tasks-tab.tsx, passes onRefresh / onSignOut and
// `embedded`). This file only filters, formats times in the browser's timezone and refreshes
// once a minute.
// Type-only import on purpose: lib/tasks.ts uses node:crypto and must stay out of the browser.

import { useEffect, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import type { Task } from "@/lib/tasks";

interface Props {
  tasks: Task[];
  statuses: string[]; // the statuses present, in display order
  error: string;
  loadedIso: string;
  embedded?: boolean; // inside the dashboard: no page chrome
  onRefresh?: () => void; // default: router.refresh() (the /tasks page)
  onSignOut?: () => void; // default: the logout form posting to /api/tasks-login
}

const PILL: Record<string, string> = {
  "Awaiting your OK": "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-200",
  "Needs you": "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  "Drafts waiting": "bg-blue-100 text-blue-900 dark:bg-blue-950 dark:text-blue-200",
  Running: "bg-zinc-200 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200",
  Failed: "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200",
  Done: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
};
const PILL_OTHER = "bg-zinc-200 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200";

const HINT: Record<string, string> = {
  "Awaiting your OK": "Nothing changed yet. Reply \"yes\" in the Gmail thread to go ahead, \"no\" to drop it.",
  Expired: "Not approved within 7 days, nothing changed. Reply in the thread to start again.",
  "Needs you": "The bot stopped to ask you something. Reply in the Gmail thread.",
  "Drafts waiting": "Changes are made. Emails are in your Gmail drafts for you to send.",
  Running: "Being worked on right now.",
  Failed: "Did not finish. The Gmail thread says what was and was not done.",
};

const noSubscription = () => () => {};
/** False on the server and during hydration, true afterwards. */
const useHydrated = () => useSyncExternalStore(noSubscription, () => true, () => false);

/** A UTC instant in the reader's own timezone. Renders the UTC text until hydrated, so the
 *  server HTML and the first browser render agree. */
function LocalTime({ iso, timeOnly = false }: { iso: string; timeOnly?: boolean }) {
  const mounted = useHydrated();
  if (!iso) return null;
  const local = new Date(iso).toLocaleString(undefined, timeOnly
    ? { hour: "numeric", minute: "2-digit" }
    : { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  return <time dateTime={iso}>{mounted ? local : `${iso.slice(0, 16).replace("T", " ")} UTC`}</time>;
}

function TaskCard({ task }: { task: Task }) {
  const [open, setOpen] = useState(false);
  const long = task.instruction.length > 280;
  return (
    <li className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className={clsx("rounded-full px-2.5 py-0.5 text-xs font-semibold", PILL[task.status] ?? PILL_OTHER)}>
          {task.status}
        </span>
        {task.number && <span className="text-xs tabular-nums text-zinc-500">#{task.number}</span>}
        <span className="ml-auto text-xs text-zinc-500"><LocalTime iso={task.receivedIso} /></span>
      </div>

      <p className={clsx("mt-3 whitespace-pre-wrap break-words text-[15px] font-medium leading-snug", long && !open && "line-clamp-4")}>
        {task.instruction || "(no instruction)"}
      </p>
      {long && (
        <button type="button" onClick={() => setOpen(!open)} className="mt-1 text-xs font-medium text-zinc-600 underline dark:text-zinc-400">
          {open ? "Show less" : "Show all"}
        </button>
      )}

      {task.understood && (
        <p className="mt-2 break-words text-sm text-zinc-700 dark:text-zinc-300">
          <span className="text-zinc-500">Understood </span>{task.understood}
        </p>
      )}

      {task.about && (
        <p className="mt-2 break-words text-sm text-zinc-600 dark:text-zinc-400">
          <span className="text-zinc-500">About </span>{task.about}
        </p>
      )}

      {task.actions.length > 0 && (
        <ul className="mt-3 space-y-1 border-l-2 border-zinc-200 pl-3 text-sm dark:border-zinc-800">
          {task.actions.map((a, i) => <li key={i} className="break-words">{a}</li>)}
        </ul>
      )}

      {task.summary && <p className="mt-3 break-words text-sm text-zinc-600 dark:text-zinc-400">{task.summary}</p>}

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500">
        {task.drafts && <span>Drafts: {task.drafts}</span>}
        {HINT[task.status] && <span>{HINT[task.status]}</span>}
        {task.threadUrl && (
          <a href={task.threadUrl} target="_blank" rel="noopener noreferrer"
            className="ml-auto font-medium text-zinc-900 underline dark:text-zinc-100">
            Open in Gmail
          </a>
        )}
      </div>
    </li>
  );
}

export function TasksView({ tasks, statuses, error, loadedIso, embedded = false, onRefresh, onSignOut }: Props) {
  const router = useRouter();
  const [filter, setFilter] = useState<string>("All");
  const refresh = onRefresh ?? router.refresh;

  // Fresh data once a minute while the page is on screen (one Sheets read per refresh).
  useEffect(() => {
    const id = setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, 60_000);
    return () => clearInterval(id);
  }, [refresh]);

  const count = (status: string) => tasks.filter((t) => t.status === status).length;
  const active = filter !== "All" && !statuses.includes(filter) ? "All" : filter;
  const shown = active === "All" ? tasks : tasks.filter((t) => t.status === active);
  const chips = [{ label: "All", n: tasks.length }, ...statuses.map((s) => ({ label: s, n: count(s) }))];

  return (
    <main className={embedded ? "mx-auto w-full max-w-3xl" : "mx-auto w-full max-w-3xl px-4 py-6 sm:py-10"}>
      <header className="flex flex-wrap items-end gap-x-4 gap-y-2">
        <div>
          <h1 className={embedded ? "text-lg font-semibold" : "text-2xl font-semibold tracking-tight"}>Claude tasks</h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Everything you have emailed to your +claude address, newest first.
          </p>
        </div>
        <div className="ml-auto flex items-center gap-3 text-xs text-zinc-500">
          <span>Updated <LocalTime iso={loadedIso} timeOnly /></span>
          <button type="button" onClick={() => refresh()}
            className="rounded-lg border border-zinc-300 px-2.5 py-1 font-medium text-zinc-800 dark:border-zinc-700 dark:text-zinc-200">
            Refresh
          </button>
          {onSignOut ? (
            <button type="button" onClick={onSignOut} className="underline">Sign out</button>
          ) : (
            <form method="post" action="/api/tasks-login">
              <input type="hidden" name="logout" value="1" />
              <button type="submit" className="underline">Sign out</button>
            </form>
          )}
        </div>
      </header>

      {error && (
        <p role="alert" className="mt-5 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          {error}
        </p>
      )}

      {tasks.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2" role="group" aria-label="Filter by status">
          {chips.map((c) => (
            <button key={c.label} type="button" aria-pressed={active === c.label} onClick={() => setFilter(c.label)}
              className={clsx(
                "rounded-full border px-3 py-1 text-sm font-medium",
                active === c.label
                  ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
                  : "border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-300",
              )}>
              {c.label} <span className="tabular-nums opacity-70">{c.n}</span>
            </button>
          ))}
        </div>
      )}

      {tasks.length === 0 && !error ? (
        <p className="mt-8 rounded-xl border border-dashed border-zinc-300 p-6 text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
          No tasks yet. Forward an email to your +claude address with an instruction on the first line,
          for example &ldquo;claude, remove them from the CT beehiiv&rdquo;. It shows up here within a few minutes.
        </p>
      ) : (
        <ul className="mt-5 space-y-3">
          {shown.map((t) => <TaskCard key={t.id} task={t} />)}
        </ul>
      )}
    </main>
  );
}
