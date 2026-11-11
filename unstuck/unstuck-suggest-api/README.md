# unstuck-suggest-api

Tiny serverless proxy (Vercel project `unstuck-suggest-api`) behind the "Suggest with AI" button
of Unstuck, the procrastination tool. It holds `GEMINI_API_KEY` server-side and answers
`POST /api/suggest` with `{ "task": "...", "previousActions": [...], "clientId": "..." }`, returning
`{ "suggestion": "...", "tooBroad": true|false }`.

## Who can call it

| Caller | How it authenticates | Rate-limited as |
|---|---|---|
| GuidedTrack version (program "Unstuck", page `/unstuck/` on programs.clearerthinking.org) | The GT service `unstuckSuggest` adds `X-Unstuck-Key` on GuidedTrack's server; it must equal the env var `UNSTUCK_GT_KEY`. The value never reaches a browser. | each run, by the `clientId` the program sends |
| Web prototype on GitHub Pages | `X-Proto-Token`, which sits in the page source and is therefore public | each IP address |

The web token works only while `UNSTUCK_WEB_TOKEN` is set on Vercel. GuidedTrack also still sends
`X-Proto-Token`, so it kept working before the key existed; once `UNSTUCK_GT_KEY` is set it no
longer needs it. With neither variable set, every call is refused.

## Safeguards against running up the Gemini bill

- Limits, all overridable by env var: per person `LIMIT_PER_CLIENT_PER_MINUTE` (6) and
  `LIMIT_PER_CLIENT_PER_DAY` (30); everyone together `LIMIT_GLOBAL_PER_MINUTE` (30) and
  `LIMIT_GLOBAL_PER_DAY` (300). Only requests that would reach Gemini count; days are UTC.
- They are kept in memory, per warm Vercel instance, so they reset when the instance is recycled
  and are not shared between instances. A visitor can also forge the `clientId` GuidedTrack
  relays. The real ceiling is therefore a requests-per-day quota on the Google Cloud project that
  owns the key (see `rollout.sh`, step 5).
- `AI_ENABLED=0` switches the endpoint off for everyone (503).
- Replies longer than 400 characters are discarded, so the endpoint is useless as a free
  general-purpose chatbot. Only the 8 most recent completed steps are sent to Gemini.
- Browsers may call it only from the GitHub Pages site or localhost (CORS). GuidedTrack's relay
  forwards only `POST /api/suggest`.

The GuidedTrack program adds its own per-person daily cap and a kill switch (`aiEnabled`), see
`guidedtrack/Unstuck.gt`.

## Model

Google Gemini (`gemini-3.5-flash` by default; set `GEMINI_MODEL` on Vercel to change it). On the
free tier Google may use inputs and outputs to improve its products; testers should know, or the
key should move to a billed project. A 503 from Gemini is retried once
(`GEMINI_RETRY_DELAY_MS`, default 700).

## Tests and deploy

- Tests: `npm test` (Node's built-in runner; Gemini is mocked).
- First switch to this version, or any time the variables need resetting: `bash rollout.sh`
  (`--keep-web` keeps the web prototype's AI). It runs the tests, sets the variables, deploys
  and checks the live endpoint without calling Gemini.
- Plain redeploy after a code change: `npx -y vercel@51 --prod` from this folder.
- `.env.gt-key` (gitignored) holds `UNSTUCK_GT_KEY`; the same value is in the GT service settings
  (program 39188, Settings > Services > unstuckSuggest > header X-Unstuck-Key).
