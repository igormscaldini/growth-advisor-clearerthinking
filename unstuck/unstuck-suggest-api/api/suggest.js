// Serverless proxy for the "Suggest with AI" button of Unstuck (the GitHub Pages web prototype
// and the GuidedTrack version). Calls Google's Gemini API; GEMINI_API_KEY stays server-side.
//
// WHO MAY CALL (environment variables on Vercel):
// - GuidedTrack: the GT service "unstuckSuggest" adds the header X-Unstuck-Key on GuidedTrack's
//   server, so the value never reaches a browser. It must equal UNSTUCK_GT_KEY. GT also sends a
//   per-run "clientId", used to rate-limit each person separately (every GT call comes from
//   GuidedTrack's servers, so the IP address is the same for all of them).
// - Web prototype: sends X-Proto-Token, which sits in the page source and is therefore PUBLIC.
//   Accepted only while UNSTUCK_WEB_TOKEN is set (to that value). Unset it to close that door.
// - AI_ENABLED=0 switches the endpoint off for everyone (kill switch).
//
// LIMITS (in memory, per warm instance: they reset when Vercel recycles the instance and are not
// shared between instances, so the hard ceiling has to be a requests-per-day quota on the Google
// Cloud project that owns GEMINI_API_KEY). Defaults, each overridable by an environment variable:
// per person 6 a minute and 30 a day; everyone together 30 a minute and 300 a day. Only requests
// that would reach Gemini count. Replies longer than MAX_SUGGESTION_LENGTH are discarded, so the
// endpoint is useless as a free general-purpose chatbot.

const crypto = require("crypto");

const MAX_TASK_LENGTH = 500;
const MAX_HISTORY_ITEMS = 8;
const MAX_HISTORY_ITEM_LENGTH = 300;
const MAX_CLIENT_ID_LENGTH = 80;
const MAX_SUGGESTION_LENGTH = 400;
// A Gemini model on the free tier (see https://ai.google.dev/gemini-api/docs/pricing).
// Override with the GEMINI_MODEL env var on Vercel if Google renames or retires it.
const MODEL = process.env.GEMINI_MODEL || "gemini-3.5-flash";
const RETRY_DELAY_MS = Number(process.env.GEMINI_RETRY_DELAY_MS || 700);

function envNumber(name, fallback) {
  const raw = process.env[name];
  if (raw === undefined || raw === "") return fallback;
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 ? n : fallback;
}

function limits() {
  return {
    clientMinute: envNumber("LIMIT_PER_CLIENT_PER_MINUTE", 6),
    clientDay: envNumber("LIMIT_PER_CLIENT_PER_DAY", 30),
    globalMinute: envNumber("LIMIT_GLOBAL_PER_MINUTE", 30),
    globalDay: envNumber("LIMIT_GLOBAL_PER_DAY", 300),
  };
}

// ---------- in-memory rate limiting ----------
let now = () => Date.now();
const minuteHits = new Map(); // key -> timestamps (ms) of the last minute
const dayCounts = new Map(); // "YYYY-MM-DD|key" -> count for that UTC day
const GLOBAL = "*";

function recentHits(key, t) {
  return (minuteHits.get(key) || []).filter((h) => t - h < 60_000);
}

// Returns null and records the call when it is allowed; otherwise "day" or "minute".
function takeSlot(clientKey) {
  const t = now();
  const day = new Date(t).toISOString().slice(0, 10);
  for (const k of dayCounts.keys()) if (!k.startsWith(day + "|")) dayCounts.delete(k);
  if (minuteHits.size > 2000) {
    for (const [k, hits] of minuteHits) if (!hits.some((h) => t - h < 60_000)) minuteHits.delete(k);
  }
  const L = limits();
  const globalDay = dayCounts.get(day + "|" + GLOBAL) || 0;
  const clientDay = dayCounts.get(day + "|" + clientKey) || 0;
  if (globalDay >= L.globalDay || clientDay >= L.clientDay) return "day";
  const globalRecent = recentHits(GLOBAL, t);
  const clientRecent = recentHits(clientKey, t);
  if (globalRecent.length >= L.globalMinute || clientRecent.length >= L.clientMinute) return "minute";
  globalRecent.push(t);
  clientRecent.push(t);
  minuteHits.set(GLOBAL, globalRecent);
  minuteHits.set(clientKey, clientRecent);
  dayCounts.set(day + "|" + GLOBAL, globalDay + 1);
  dayCounts.set(day + "|" + clientKey, clientDay + 1);
  return null;
}

// ---------- callers ----------
function sameSecret(given, expected) {
  if (typeof given !== "string" || !expected) return false;
  const a = Buffer.from(given);
  const b = Buffer.from(expected);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

// Env values are trimmed: a value pasted or piped into Vercel can carry a trailing newline.
function env(name) {
  return String(process.env[name] || "").trim();
}

// "gt", "web" or null.
function callerOf(req) {
  if (sameSecret(req.headers["x-unstuck-key"], env("UNSTUCK_GT_KEY"))) return "gt";
  if (sameSecret(req.headers["x-proto-token"], env("UNSTUCK_WEB_TOKEN"))) return "web";
  return null;
}

// Origins allowed to call this endpoint from a browser: the GitHub Pages site and local dev
// servers (test index.html through http://localhost, e.g. python3 -m http.server). "null" (a
// page opened from file://) is not allowed: sandboxed iframes on any website also send "null".
// GuidedTrack calls come from its server, so CORS does not apply to them.
const ALLOWED_ORIGINS = ["https://igormscaldini.github.io"];
function isAllowedOrigin(origin) {
  if (!origin) return false;
  if (ALLOWED_ORIGINS.includes(origin)) return true;
  return /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin);
}

function setCors(req, res) {
  const origin = req.headers.origin;
  if (isAllowedOrigin(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
    res.setHeader("Vary", "Origin");
  }
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, X-Proto-Token");
}

async function handler(req, res) {
  setCors(req, res);

  if (req.method === "OPTIONS") {
    res.status(204).end();
    return;
  }
  if (req.method !== "POST") {
    res.status(405).json({ error: "Method not allowed" });
    return;
  }
  if (!env("UNSTUCK_GT_KEY") && !env("UNSTUCK_WEB_TOKEN")) {
    res.status(500).json({ error: "Server not configured" });
    return;
  }
  const caller = callerOf(req);
  if (!caller) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }
  if (env("AI_ENABLED") === "0") {
    res.status(503).json({ error: "AI suggestions are switched off", limit: "off" });
    return;
  }

  const body = req.body && typeof req.body === "object" ? req.body : {};
  const task = (body.task ? String(body.task) : "").trim();
  if (!task) {
    res.status(400).json({ error: "Missing task" });
    return;
  }
  if (task.length > MAX_TASK_LENGTH) {
    res.status(400).json({ error: "Task description too long" });
    return;
  }

  const previousActions = Array.isArray(body.previousActions)
    ? body.previousActions
        .filter((a) => typeof a === "string" && a.trim())
        .map((a) => a.trim().slice(0, MAX_HISTORY_ITEM_LENGTH))
        .slice(-MAX_HISTORY_ITEMS)
    : [];

  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    res.status(500).json({ error: "Server not configured" });
    return;
  }

  // Who to count this request against: each GuidedTrack run separately (all GT calls share
  // GuidedTrack's IP), and web visitors by IP.
  const ip =
    (req.headers["x-forwarded-for"] || "").split(",")[0].trim() ||
    req.socket?.remoteAddress ||
    "unknown";
  const clientId = typeof body.clientId === "string" ? body.clientId.trim().slice(0, MAX_CLIENT_ID_LENGTH) : "";
  const clientKey = caller === "gt" ? "gt:" + (clientId || "no-client-id") : "ip:" + ip;
  const limited = takeSlot(clientKey);
  if (limited === "day") {
    res.status(429).json({ error: "Daily limit reached", limit: "day" });
    return;
  }
  if (limited === "minute") {
    res.status(429).json({ error: "Too many requests, slow down a bit", limit: "minute" });
    return;
  }

  const system =
    "You help someone who is procrastinating find ONE small thing they could do in the next 10 " +
    "minutes about a task they describe. Assume the person has some baseline capability and can " +
    "handle producing a small amount of real work — not just a single trivial warm-up action — " +
    "but they currently have LOW motivation and may not have all the specifics loaded in their " +
    "head, so avoid asking them to make big judgment calls, weigh priorities among many options, " +
    "or draw on specialized knowledge they may not have.\n\n" +
    "If the person has already completed earlier steps on this same task (given below), suggest " +
    "the NEXT logical step that builds on that progress — don't repeat what they already did or " +
    "suggest something disconnected from it.\n\n" +
    "Hard rules for the suggestion:\n" +
    "- It must not require weighing multiple priorities or specialized expertise (e.g. never " +
    "\"list the 3-5 key topics that matter most\" — deciding what matters most is often the hard " +
    "part they're stuck on).\n" +
    "- It's fine for the suggestion to ask for a bit of real, rough output — a short paragraph, a " +
    "few bullet points, a first pass at something — as long as it's clearly low-stakes, " +
    "reversible, and doesn't require them to already know the \"right\" answer.\n" +
    "- If the task involves specialized/technical content the person may not have memorized, " +
    "suggest reviewing/skimming existing material rather than producing new expert content from " +
    "memory.\n" +
    "- A good test: could someone with only casual familiarity with this task start doing this " +
    "within a few seconds of reading it, and finish in well under 10 minutes without needing " +
    "outside expertise?\n\n" +
    "Examples (BAD = too big/assumes expertise, TOO TINY = undersized, don't do this either, " +
    "GOOD = right-sized):\n" +
    "Task: \"Preparing slides for Thursday's board meeting\"\n" +
    "  BAD: \"List the 3-5 key topics you need to cover and create a blank slide for each.\"\n" +
    "  TOO TINY: \"Open a blank slide deck and just type the meeting title on slide one.\"\n" +
    "  GOOD: \"Open a blank slide deck, type the meeting title on slide one, and add 2-3 more " +
    "slides with rough placeholder headers for whatever topics come to mind first — they don't " +
    "need to be right.\"\n" +
    "Task: \"Writing the first draft of a quarterly report for my manager\"\n" +
    "  BAD: \"Write the Executive Summary with 3-4 bullet points of your biggest accomplishments.\"\n" +
    "  TOO TINY: \"Open a blank document and write one rough sentence about what this report is " +
    "about.\"\n" +
    "  GOOD: \"Open a blank document and write a rough 3-4 sentence paragraph about what this " +
    "report covers and why — it's fine if it's messy, you can fix it later.\"\n" +
    "Task: \"Studying for my chemistry exam next week\"\n" +
    "  BAD: \"Write out the electron configurations for the first 20 elements.\"\n" +
    "  TOO TINY: \"Open your chemistry notes or textbook and reread just the first page.\"\n" +
    "  GOOD: \"Open your chemistry notes or textbook and skim the next 2-3 pages, jotting down " +
    "anything that looks unfamiliar.\"\n\n" +
    "Judge BROAD only when the description gives you almost nothing to work with (e.g. single " +
    "vague words or phrases like \"life stuff\", \"my project\", \"work\", \"that thing\", " +
    "\"school\"). If the task names a specific deliverable, person, deadline, event, or subject " +
    "matter — even briefly — treat it as OK, not BROAD, even if some details are still unstated.\n\n" +
    "Respond in EXACTLY this two-line format, nothing else, no markdown:\n" +
    "Line 1: the single word OK, or the single word BROAD.\n" +
    "Line 2: one or two short sentences, written as a direct instruction telling them what to do " +
    "(never a question, never a request for more detail, never \"it depends\" or similar hedging) " +
    "— the suggested action, following the hard rules above. Even if line 1 is BROAD, you MUST " +
    "still invent a concrete, reasonable, generic best-guess action on line 2 — do not ask a " +
    "clarifying question and do not refuse.";

  let userContent = `Task: ${task}`;
  if (previousActions.length) {
    const steps = previousActions.map((a, i) => `${i + 1}. ${a}`).join("\n");
    userContent += `\n\nSteps already completed on this task, in order (most recent last):\n${steps}`;
  }

  try {
    const callGemini = () => fetch(
      "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":generateContent",
      {
        method: "POST",
        headers: { "content-type": "application/json", "x-goog-api-key": apiKey },
        body: JSON.stringify({
          system_instruction: { parts: [{ text: system }] },
          contents: [{ role: "user", parts: [{ text: userContent }] }],
          // Generous cap: on "thinking" Gemini models, reasoning tokens count toward
          // this limit, and a tight cap can leave no room for the visible answer.
          generationConfig: { maxOutputTokens: 1024, temperature: 0.7 },
        }),
      }
    );
    // Gemini's free tier often answers 503 UNAVAILABLE for a moment; one retry usually works.
    let upstream = await callGemini();
    if (upstream.status === 503) {
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
      upstream = await callGemini();
    }

    if (!upstream.ok) {
      const errText = await upstream.text();
      console.error("Gemini API error", upstream.status, errText);
      let errStatus = "";
      try { errStatus = JSON.parse(errText).error.status || ""; } catch (_) { /* not JSON */ }
      res.status(502).json({
        error: "AI suggestion failed (Gemini " + upstream.status + (errStatus ? " " + errStatus : "") + ")",
      });
      return;
    }

    const data = await upstream.json();
    // Visible answer = the non-"thought" text parts of the first candidate.
    const candidate = (data.candidates || [])[0] || {};
    const parts = ((candidate.content || {}).parts || []).filter((p) => !p.thought);
    const raw = parts.map((p) => p.text || "").join("").trim();

    const lines = raw.split("\n").map((l) => l.trim()).filter(Boolean);
    let tooBroad = false;
    let suggestion = raw;
    // Line 1 is OK or BROAD; tolerate harmless slips such as "OK." or "**OK**".
    const label = lines.length >= 2 ? lines[0].replace(/[*_.:\s]/g, "").toUpperCase() : "";
    if (label === "OK" || label === "BROAD") {
      tooBroad = label === "BROAD";
      suggestion = lines.slice(1).join(" ");
    }
    // The prompt asks for one or two short sentences. Anything empty or much longer means the
    // model was steered elsewhere (e.g. instructions typed into the task), so nothing is returned.
    if (!suggestion || suggestion.length > MAX_SUGGESTION_LENGTH) {
      console.error("suggest.js: discarded a reply of", suggestion.length, "characters");
      res.status(502).json({ error: "AI suggestion failed" });
      return;
    }

    res.status(200).json({ suggestion, tooBroad });
  } catch (err) {
    console.error("suggest.js error", err);
    res.status(500).json({ error: "AI suggestion failed" });
  }
}

module.exports = handler;
// Test hooks (not used by Vercel).
module.exports._resetLimits = () => { minuteHits.clear(); dayCounts.clear(); };
module.exports._setNow = (fn) => { now = fn || (() => Date.now()); };
