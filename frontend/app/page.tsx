import fs from "node:fs/promises";
import path from "node:path";
import { Dashboard } from "@/components/dashboard";
import type { Snapshot } from "@/lib/snapshot";

export const revalidate = 60; // re-read the static file at most once per minute

async function loadSnapshot(): Promise<Snapshot> {
  const file = path.join(process.cwd(), "public", "snapshot.json");
  const raw = await fs.readFile(file, "utf8");
  return JSON.parse(raw) as Snapshot;
}

export default async function Page() {
  const snapshot = await loadSnapshot();
  return <Dashboard snapshot={snapshot} />;
}
