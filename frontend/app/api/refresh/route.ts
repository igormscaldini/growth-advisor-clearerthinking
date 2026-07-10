// POST /api/refresh — triggers the "Fetch dashboard snapshot" GitHub Action
// (workflow_dispatch) so the snapshot is regenerated with data up to "now".
// Requires a server-side GitHub token with actions:write on the repo.
//
// Env vars (set in Vercel → Project → Settings → Environment Variables):
//   GH_DISPATCH_TOKEN  (required) — a fine-grained PAT with "Actions: read and write"
//   GH_REPO            (optional) — defaults to igormscaldini/growth-advisor-clearerthinking
//   GH_WORKFLOW        (optional) — defaults to fetch-snapshot.yml
//   GH_REF             (optional) — branch to run on, defaults to main

export async function POST() {
  const token = process.env.GH_DISPATCH_TOKEN;
  const repo = process.env.GH_REPO ?? "igormscaldini/growth-advisor-clearerthinking";
  const workflow = process.env.GH_WORKFLOW ?? "fetch-snapshot.yml";
  const ref = process.env.GH_REF ?? "main";

  if (!token) {
    return Response.json(
      { ok: false, error: "Refresh isn't configured yet: set GH_DISPATCH_TOKEN in Vercel." },
      { status: 500 },
    );
  }

  const res = await fetch(
    `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({ ref }),
    },
  );

  if (res.status === 204) {
    return Response.json({ ok: true });
  }
  const detail = await res.text();
  return Response.json(
    { ok: false, error: `GitHub API ${res.status}: ${detail.slice(0, 300)}` },
    { status: 502 },
  );
}
