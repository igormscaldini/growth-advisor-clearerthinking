"use client";

import { useState } from "react";

type State = "idle" | "loading" | "done" | "error";

export function RefreshButton() {
  const [state, setState] = useState<State>("idle");
  const [msg, setMsg] = useState("");

  async function onClick() {
    setState("loading");
    setMsg("");
    try {
      const r = await fetch("/api/refresh", { method: "POST" });
      const j = (await r.json()) as { ok: boolean; error?: string };
      if (j.ok) {
        setState("done");
        setMsg("Refresh started. New data lands in a few minutes — reload the page shortly.");
      } else {
        setState("error");
        setMsg(j.error ?? "Couldn't start the refresh.");
      }
    } catch {
      setState("error");
      setMsg("Network error starting the refresh.");
    }
  }

  return (
    <div className="flex items-center gap-2 mt-1">
      <button
        onClick={onClick}
        disabled={state === "loading"}
        className="inline-flex items-center gap-1.5 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-2.5 py-1 text-xs font-medium text-zinc-700 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        title="Regenerate the dashboard snapshot with data up to now"
      >
        {state === "loading" ? "Refreshing…" : "↻ Refresh data"}
      </button>
      {msg ? (
        <span
          className={`text-xs ${
            state === "error" ? "text-red-500 dark:text-red-400" : "text-zinc-500 dark:text-zinc-400"
          }`}
        >
          {msg}
        </span>
      ) : null}
    </div>
  );
}
