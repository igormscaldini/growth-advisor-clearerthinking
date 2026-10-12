import { test } from "node:test";
import assert from "node:assert/strict";
import { emailHash, hashesFromSubscriptions, makeCache, normalizeHash } from "./member-check.ts";

test("emailHash is MD5 of the trimmed, lowercased address", () => {
  // md5("hello") is the textbook value; the function must trim and lowercase before hashing.
  assert.equal(emailHash("  HeLLo "), "5d41402abc4b2a76b9719d911017c592");
  assert.equal(emailHash("Igor@Example.com"), emailHash("igor@example.com"));
});

test("normalizeHash accepts a 32-hex MD5 in any case and rejects everything else", () => {
  assert.equal(normalizeHash(" 5D41402ABC4B2A76B9719D911017C592 "), "5d41402abc4b2a76b9719d911017c592");
  assert.equal(normalizeHash("5d41402abc4b2a76b9719d911017c59"), null); // 31 chars
  assert.equal(normalizeHash("{{subscriber_email_hash}}"), null); // merge tag not rendered
  assert.equal(normalizeHash(""), null);
  assert.equal(normalizeHash(null), null);
  assert.equal(normalizeHash(undefined), null);
});

test("hashesFromSubscriptions keeps active and past_due members with an expanded customer email", () => {
  const hashes = hashesFromSubscriptions([
    { status: "active", customer: { email: "A@x.com" } },
    { status: "past_due", customer: { email: "b@x.com" } },
    { status: "canceled", customer: { email: "c@x.com" } },
    { status: "trialing", customer: { email: "d@x.com" } },
    { status: "active", customer: "cus_notexpanded" },
    { status: "active", customer: { email: null } },
    { status: "active", customer: { deleted: true } },
    { status: "active" },
    { status: "active", customer: { email: "a@x.com" } }, // same person twice: one hash
  ]);
  assert.deepEqual([...hashes].sort(), [emailHash("a@x.com"), emailHash("b@x.com")].sort());
  assert.equal(hashes.size, 2);
});

test("makeCache loads once per ttl and reloads after it", async () => {
  let loads = 0;
  const cache = makeCache<number>(1000);
  const load = async () => ++loads;
  assert.equal(await cache.get(load, 0), 1);
  assert.equal(await cache.get(load, 999), 1); // cached
  assert.equal(await cache.get(load, 1000), 2); // expired
  assert.equal(loads, 2);
});

test("makeCache keeps the old value when a reload fails, and clear() forces a reload", async () => {
  const cache = makeCache<string>(10);
  assert.equal(await cache.get(async () => "first", 0), "first");
  await assert.rejects(cache.get(async () => { throw new Error("stripe down"); }, 50));
  // the failed reload did not clobber the cached value, but it is expired, so the next good load replaces it
  assert.equal(await cache.get(async () => "second", 60), "second");
  cache.clear();
  assert.equal(await cache.get(async () => "third", 61), "third");
});
