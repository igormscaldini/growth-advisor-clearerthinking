# unstuck-suggest-api

Tiny serverless proxy for the "Suggest with AI" button of Unstuck, the procrastination tool. It has
two callers:

- the web prototype on GitHub Pages (https://igormscaldini.github.io/unstuck-prototype/), straight
  from the browser;
- the GuidedTrack version (program "Unstuck", page `/unstuck/` on programs.clearerthinking.org),
  through the GuidedTrack service `unstuckSuggest`. That request leaves GuidedTrack's server, so
  every GuidedTrack user shares one IP as far as the per-IP rate limit here is concerned.

Holds `GEMINI_API_KEY` server-side so neither frontend exposes it. Both call `POST /api/suggest`
with `{ "task": "...", "previousActions": [...] }` and the `X-Proto-Token` header, and get back
`{ "suggestion": "...", "tooBroad": true|false }`. A 503 from Gemini is retried once before an
error is returned (wait set by `GEMINI_RETRY_DELAY_MS`, default 700).

The model is Google Gemini on its free tier (`gemini-3.5-flash` by default; set `GEMINI_MODEL` on
Vercel to change it). Note that Google may use free-tier inputs and outputs to improve its
products, so this is fine for an internal prototype but should be revisited before any public
release.

Not hardened for public use beyond this: see the comment at the top of `api/suggest.js` for the
current (deliberately lightweight) abuse-mitigation approach and what to upgrade if this goes
beyond internal team testing.

`api/technique.js` is an older, unused endpoint that still targets the Anthropic API.

Tests: `npm test` (Node's built-in test runner; the Gemini call is mocked).

Deploy: `npx vercel --prod` (from this directory). Requires the `GEMINI_API_KEY` env var to be set
on the Vercel project (`npx vercel env add GEMINI_API_KEY production`).
