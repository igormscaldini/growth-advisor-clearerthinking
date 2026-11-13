import fs from "node:fs/promises";
import path from "node:path";
import { Dashboard } from "@/components/dashboard";
import type { Snapshot } from "@/lib/snapshot";
import { normalizeSnapshot } from "@/lib/normalize";

export const revalidate = 60; // re-read the static file at most once per minute

async function loadSnapshot(): Promise<Snapshot> {
  const file = path.join(process.cwd(), "public", "snapshot.json");
  const raw = await fs.readFile(file, "utf8");
  // A source that failed during the fetch is an {"error": ...} block in the file; normalize so the
  // page always renders (an un-normalized block killed every deploy during the 2026-11-13 GA4 outage).
  return normalizeSnapshot(JSON.parse(raw) as Snapshot);
}

export default async function Page() {
  const snapshot = await loadSnapshot();
  return <Dashboard snapshot={snapshot} />;
}
