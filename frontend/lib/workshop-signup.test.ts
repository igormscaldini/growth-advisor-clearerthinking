import { test } from "node:test";
import assert from "node:assert/strict";
import { basicAuthOk, findEmailRow, normalizeSignup, parseBody, toRow } from "./workshop-signup.ts";

test("parseBody accepts JSON and form bodies", () => {
  assert.deepEqual(parseBody("application/json", '{"email":"a@b.co","src":"x"}'), { email: "a@b.co", src: "x" });
  assert.deepEqual(parseBody(null, '{"email":"a@b.co"}'), { email: "a@b.co" });
  assert.deepEqual(parseBody("application/x-www-form-urlencoded", "email=a%40b.co&firstName=Ann"), { email: "a@b.co", firstName: "Ann" });
  assert.deepEqual(parseBody("application/json", "not json"), {});
});

test("normalizeSignup lower-cases and trims, rejects rows without an email", () => {
  const s = normalizeSignup({ email: "  Ann@Example.COM ", firstName: " Ann ", question: null, src: "ignored" });
  assert.deepEqual(s, { email: "ann@example.com", firstName: "Ann", question: "" });
  assert.equal(normalizeSignup({ email: "nope" }), null);
  assert.equal(normalizeSignup({}), null);
});

test("basicAuthOk matches only the exact user:password pair", () => {
  const header = "Basic " + Buffer.from("gt:secret").toString("base64");
  assert.equal(basicAuthOk(header, "gt", "secret"), true);
  assert.equal(basicAuthOk(header, "gt", "secre"), false);
  assert.equal(basicAuthOk(header, "gt", "secretx"), false);
  assert.equal(basicAuthOk("Bearer abc", "gt", "secret"), false);
  assert.equal(basicAuthOk(null, "gt", "secret"), false);
  assert.equal(basicAuthOk(header, undefined, "secret"), false);
});

test("findEmailRow returns the 1-based row, skipping the header", () => {
  const col = [["Email"], ["a@x.io"], [], ["B@Y.io "]];
  assert.equal(findEmailRow(col, "a@x.io"), 2);
  assert.equal(findEmailRow(col, "b@y.io"), 4);
  assert.equal(findEmailRow(col, "email"), 0);
  assert.equal(findEmailRow(col, "zz@z.io"), 0);
  assert.equal(findEmailRow([], "a@x.io"), 0);
});

test("toRow lays out the sheet columns", () => {
  const row = toRow({ email: "a@x.io", firstName: "A", question: "Q?" }, new Date("2026-09-16T12:34:56.789Z"));
  assert.deepEqual(row, ["2026-09-16 12:34:56", "a@x.io", "A", "Q?"]);
});
