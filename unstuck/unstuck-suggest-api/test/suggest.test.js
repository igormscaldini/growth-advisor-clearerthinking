const test = require("node:test");
const assert = require("node:assert/strict");

process.env.GEMINI_API_KEY = "test-key";
const handler = require("../api/suggest.js");
const TOKEN = "Vb2jxJSOSr2RwZxEy12jgJhECuYnzVsm";

let ipCounter = 0;
function makeReq({ method = "POST", origin = "https://igormscaldini.github.io", token = TOKEN, body } = {}) {
  ipCounter += 1; // distinct IP per request so the in-memory rate limit never trips
  return {
    method,
    headers: { origin, "x-proto-token": token, "x-forwarded-for": "10.0.0." + ipCounter },
    body,
  };
}
function makeRes() {
  const res = { headers: {}, statusCode: 200, body: undefined, ended: false };
  res.setHeader = (k, v) => { res.headers[k.toLowerCase()] = v; };
  res.status = (c) => { res.statusCode = c; return res; };
  res.json = (b) => { res.body = b; res.ended = true; };
  res.end = () => { res.ended = true; };
  return res;
}
function geminiReply(text) {
  return { ok: true, status: 200, json: async () => ({ candidates: [{ content: { parts: [{ text }] } }] }) };
}
async function run(req, fetchImpl) {
  const original = global.fetch;
  const calls = [];
  global.fetch = async (url, opts) => { calls.push({ url, opts }); return fetchImpl(url, opts); };
  const res = makeRes();
  try { await handler(req, res); } finally { global.fetch = original; }
  return { res, calls };
}

test("preflight echoes an allowed origin and answers 204", async () => {
  const { res } = await run(makeReq({ method: "OPTIONS" }), () => { throw new Error("no fetch expected"); });
  assert.equal(res.statusCode, 204);
  assert.equal(res.headers["access-control-allow-origin"], "https://igormscaldini.github.io");
});

test("local-testing origins (null and localhost) are allowed", async () => {
  for (const origin of ["null", "http://localhost:8000", "http://127.0.0.1:5500"]) {
    const { res } = await run(makeReq({ method: "OPTIONS", origin }), () => {});
    assert.equal(res.headers["access-control-allow-origin"], origin, origin);
  }
});

test("an unknown origin gets no allow-origin header", async () => {
  const { res } = await run(makeReq({ method: "OPTIONS", origin: "https://evil.example" }), () => {});
  assert.equal(res.headers["access-control-allow-origin"], undefined);
});

test("wrong proto token is rejected with 401", async () => {
  const { res } = await run(makeReq({ token: "nope", body: { task: "x" } }), () => {});
  assert.equal(res.statusCode, 401);
});

test("missing task is rejected with 400", async () => {
  const { res } = await run(makeReq({ body: { task: "   " } }), () => {});
  assert.equal(res.statusCode, 400);
});

test("happy path: OK line is stripped, suggestion returned, Gemini called correctly", async () => {
  const { res, calls } = await run(
    makeReq({ body: { task: "Write the quarterly report", previousActions: ["Opened the doc"] } }),
    () => geminiReply("OK\nWrite a rough three-sentence paragraph about what the report covers.")
  );
  assert.equal(res.statusCode, 200);
  assert.deepEqual(res.body, {
    suggestion: "Write a rough three-sentence paragraph about what the report covers.",
    tooBroad: false,
  });
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /generativelanguage\.googleapis\.com\/v1beta\/models\/gemini-[^/]+:generateContent$/);
  assert.equal(calls[0].opts.headers["x-goog-api-key"], "test-key");
  const sent = JSON.parse(calls[0].opts.body);
  assert.ok(sent.system_instruction.parts[0].text.includes("Line 1: the single word OK"));
  assert.ok(sent.contents[0].parts[0].text.includes("Task: Write the quarterly report"));
  assert.ok(sent.contents[0].parts[0].text.includes("1. Opened the doc"));
});

test("BROAD line sets tooBroad", async () => {
  const { res } = await run(makeReq({ body: { task: "work" } }), () => geminiReply("BROAD\nOpen your task list and pick the first item."));
  assert.equal(res.body.tooBroad, true);
  assert.equal(res.body.suggestion, "Open your task list and pick the first item.");
});

test("thought parts from thinking models are ignored", async () => {
  const { res } = await run(makeReq({ body: { task: "Call the dentist" } }), async () => ({
    ok: true, status: 200,
    json: async () => ({ candidates: [{ content: { parts: [{ thought: true, text: "reasoning..." }, { text: "OK\nFind the clinic's number and save it in your phone." }] } }] }),
  }));
  assert.equal(res.body.suggestion, "Find the clinic's number and save it in your phone.");
});

test("upstream error surfaces the Gemini status in the message", async () => {
  const { res } = await run(makeReq({ body: { task: "Study for the exam" } }), async () => ({
    ok: false, status: 429, text: async () => JSON.stringify({ error: { code: 429, status: "RESOURCE_EXHAUSTED", message: "quota" } }),
  }));
  assert.equal(res.statusCode, 502);
  assert.match(res.body.error, /Gemini 429 RESOURCE_EXHAUSTED/);
});

test("missing API key returns 500 without calling Gemini", async () => {
  const saved = process.env.GEMINI_API_KEY;
  delete process.env.GEMINI_API_KEY;
  try {
    const { res, calls } = await run(makeReq({ body: { task: "x" } }), () => geminiReply("OK\ny"));
    assert.equal(res.statusCode, 500);
    assert.equal(calls.length, 0);
  } finally { process.env.GEMINI_API_KEY = saved; }
});
