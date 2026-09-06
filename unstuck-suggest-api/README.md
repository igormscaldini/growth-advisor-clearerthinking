# unstuck-suggest-api

Tiny serverless proxy for the "Unstuck" procrastination-tool prototype (hosted on GitHub Pages at
https://igormscaldini.github.io/unstuck-prototype/).

Holds `GEMINI_API_KEY` server-side so the static GitHub Pages frontend never exposes it. The
frontend's "Suggest with AI" button calls `POST /api/suggest` here with
`{ "task": "...", "previousActions": [...] }` and gets back
`{ "suggestion": "...", "tooBroad": true|false }`.

The model is Google Gemini on its free tier (`gemini-3.5-flash` by default; set `GEMINI_MODEL` on
Vercel to change it). Note that Google may use free-tier inputs and outputs to improve its
products, so this is fine for an internal prototype but should be revisited before any public
release.

Not hardened for public use beyond this — see the comment at the top of `api/suggest.js` for the
current (deliberately lightweight) abuse-mitigation approach and what to upgrade if this goes
beyond internal team testing.

`api/technique.js` is an older, unused endpoint that still targets the Anthropic API.

Tests: `npm test` (Node's built-in test runner; the Gemini call is mocked).

Deploy: `npx vercel --prod` (from this directory). Requires the `GEMINI_API_KEY` env var to be set
on the Vercel project (`npx vercel env add GEMINI_API_KEY production`).
