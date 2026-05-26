# Deploy guide — Vercel dashboard + GitHub Actions snapshot

The dashboard is now split into two pieces:

- **Data layer (Python)** — `fetch_snapshot.py` calls the existing `data_layer.py`, writes `frontend/public/snapshot.json`.
  Runs on a GitHub Actions cron every 30 min.
- **UI (Next.js)** — `frontend/` reads `snapshot.json` and renders the dashboard. Deployed to Vercel.

The Streamlit version (`dashboard.py`) is still committed for now. Once the new dashboard is live you can delete it.

---

## 1. Add GitHub Actions secrets

Go to: `https://github.com/igormscaldini/growth-advisor-clearerthinking/settings/secrets/actions` → **New repository secret**.

Add each of these (values come from your local `.env` and `secrets/*.json`):

| Secret name | Value source |
|---|---|
| `GA4_PROPERTY_ID` | `.env` |
| `GSC_SITE_URL` | `.env` |
| `STRIPE_SECRET_KEY` | `.env` |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | `.env` |
| `GOOGLE_ADS_CUSTOMER_ID` | `.env` |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | `.env` |
| `BEEHIIV_API_KEY` | `.env` |
| `BEEHIIV_PUB_CLEARER_THINKING` | `.env` |
| `OAUTH_CLIENT_JSON` | full contents of `secrets/oauth-client.json` |
| `GOOGLE_TOKEN_JSON` | full contents of `secrets/ga4-token.json` |

For the two `*_JSON` secrets, paste the raw JSON (including braces). The cron job writes them to `secrets/oauth-client.json` and `secrets/ga4-token.json` at the start of each run.

## 2. Run the workflow manually once

Push the changes (workflow + Next.js app), then trigger a manual run to make sure secrets are wired correctly:

```bash
git add .github/workflows/fetch-snapshot.yml fetch_snapshot.py frontend/
git commit -m "Add Vercel dashboard + snapshot cron"
git push
```

Then in GitHub:
- Actions tab → **Fetch dashboard snapshot** → **Run workflow** → confirm.
- It should complete in ~30s and commit a new `frontend/public/snapshot.json`.

## 3. Deploy the frontend to Vercel

1. Go to https://vercel.com/new
2. Import `igormscaldini/growth-advisor-clearerthinking`
3. **Root Directory**: set to `frontend`
4. Framework Preset: **Next.js** (auto-detected)
5. Leave Build / Output Directory at defaults
6. **No environment variables needed** — the snapshot is committed to the repo
7. Click **Deploy**

After ~1 minute you'll have a live URL like `growth-advisor-clearerthinking.vercel.app`. The dashboard never sleeps.

## 4. (Optional) Custom domain

In Vercel project settings → **Domains**, add e.g. `dashboard.clearerthinking.org`. Vercel walks you through DNS.

---

## How updates flow

```
   API change in data_layer.py
        │
        ▼
   Push to main
        │
        ├──► GitHub Actions cron (every 30 min):
        │        runs fetch_snapshot.py
        │        commits new snapshot.json
        │
        └──► Vercel auto-deploys on every commit to main
                 → new snapshot reflected in the dashboard
```

## Updating manual revenue lines

Edit the `MANUAL_REVENUE` dict at the top of `fetch_snapshot.py` and push. Next cron run picks it up.

## Local dev

```bash
# Refresh the snapshot
python fetch_snapshot.py

# Run the frontend
cd frontend && npm run dev
```

The Streamlit dashboard still works (`streamlit run dashboard.py`) — both can coexist while you verify the new one.
