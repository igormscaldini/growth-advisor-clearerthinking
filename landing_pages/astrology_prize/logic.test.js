// Run with: node --test landing_pages/astrology_prize/logic.test.js
const test = require('node:test');
const assert = require('node:assert/strict');
const L = require('./logic.js');

const close = (a, b, tol) => assert.ok(Math.abs(a - b) <= tol, `${a} is not within ${tol} of ${b}`);

test('binomial tail: cases worked by hand', () => {
  close(L.binomTail(1, 1, 0.2), 0.2, 1e-12);            // one pick from five
  close(L.binomTail(2, 1, 0.5), 0.75, 1e-12);           // at least one head in two flips
  close(L.binomTail(3, 0, 0.3), 1, 1e-12);              // at least zero is certain
  close(L.binomTail(3, 4, 0.3), 0, 1e-12);              // more hits than tries is impossible
  // 11 or 12 of 12 at p = 0.2: 12 * 0.2^11 * 0.8 + 0.2^12 = 1.96608e-7 + 4.096e-9
  close(L.binomTail(12, 11, 0.2), 2.00704e-7, 1e-12);
});

test('chance distribution matches the study report table', () => {
  const pct = L.chancePct(12, 0.2);
  assert.equal(pct.length, 13);
  close(pct.reduce((a, b) => a + b, 0), 100, 1e-9);
  // "Expected % if they were all guessing at random" for 0..7 in the report
  [6.9, 20.6, 28.3, 23.6, 13.3, 5.3, 1.6, 0.3].forEach((expected, k) => close(pct[k], expected, 0.06));
});

test('the 2024 score distribution is transcribed consistently', () => {
  const s = L.STUDY_2024;
  assert.equal(s.scorePct.length, L.CONFIG.questions + 1);
  close(s.scorePct.reduce((a, b) => a + b, 0), 100, 0.11);
  // its mean must reproduce the reported average of 2.49 (20.4 + 46 + 84.9 + 68.4 + 29.5 = 249.2)
  close(s.scorePct.reduce((a, v, k) => a + v * k, 0) / 100, s.meanScore, 0.005);
  assert.equal(s.scorePct.findLastIndex((v) => v > 0), s.bestScore);
});

test('odds wording', () => {
  assert.equal(L.oneInText(L.luckyWinProbability()), '5 million');   // 1 in 4,982,462
  assert.equal(L.oneInText(0.2), '5');
  assert.equal(L.oneInText(1 / 16077), '16,000');
  assert.equal(L.oneInText(1 / 2.6e9), '3 billion');
  assert.equal(L.chanceMean(), 2.4);
  assert.equal(L.formatMoney(100000), '$100,000');
  assert.equal(L.formatPct(0), '0%');
  assert.equal(L.formatPct(0.05), 'under 0.1%');
  assert.equal(L.formatPct(28.3), '28.3%');
});

test('seeded generator is reproducible and stays in [0, 1)', () => {
  const a = L.mulberry32(42), b = L.mulberry32(42), c = L.mulberry32(43);
  const xs = Array.from({ length: 1000 }, () => a());
  assert.deepEqual(xs.slice(0, 5), Array.from({ length: 5 }, () => b()));
  assert.notEqual(xs[0], c());
  assert.ok(xs.every((x) => x >= 0 && x < 1));
});

test('blind game: synthetic generators with a known score', () => {
  // a generator stuck on one value makes the pick and the real chart coincide every time
  assert.equal(L.simulateScore(() => 0), 12);
  assert.equal(L.simulateScore(() => 0.999999), 12);
  // alternating low/high: the pick is always card 0 and the real chart always card 4
  let flip = false;
  assert.equal(L.simulateScore(() => ((flip = !flip) ? 0 : 0.99)), 0);
  assert.deepEqual(L.playRound(() => 0.5, 2, 5), { real: 2, hit: true });
  assert.deepEqual(L.playRound(() => 0.5, 0, 5), { real: 2, hit: false });
});

test('blind game: long-run average is 12 / 5 = 2.4', () => {
  const rand = L.mulberry32(2024);
  const games = 100000;
  let total = 0, most = 0;
  for (let i = 0; i < games; i++) { const s = L.simulateScore(rand); total += s; most = Math.max(most, s); }
  close(total / games, 2.4, 0.03);          // standard error is about 0.004
  assert.ok(most < L.CONFIG.bar);           // 100,000 blind games should not reach the bar (expected 0.02 times)
});

test('verdicts follow the 2024 distribution', () => {
  assert.match(L.verdict(0).detail, /^5\.3% of the 152 astrologers/);
  assert.match(L.verdict(2).headline, /Right where the astrologers landed/);
  assert.match(L.verdict(3).detail, /^28\.3% .* scored exactly 3\./);
  assert.match(L.verdict(4).headline, /outscored 77% of the astrologers/);   // 5.3 + 20.4 + 23.0 + 28.3
  assert.match(L.verdict(5).headline, /tied the best/);
  assert.match(L.verdict(6).headline, /beat all 152 astrologers/);
  assert.match(L.verdict(10).headline, /beat all 152 astrologers/);
  assert.match(L.verdict(11).headline, /won \$100,000/);
  assert.match(L.verdict(12).detail, /once in 5 million tries/);
});

test('share links carry the text, the page and the campaign tags', () => {
  const page = 'https://example.org/prize';
  const text = L.shareText('result', 3);
  const links = L.shareLinks(page, text, 'result');
  assert.deepEqual(Object.keys(links), L.NETWORKS.map((n) => n.id));
  for (const [id, item] of Object.entries(links)) {
    assert.ok(item.link.startsWith(page + '?utm_source=' + id + '&'), id);
    assert.match(item.link, /utm_campaign=astrology_prize&utm_content=result$/);
    assert.ok(decodeURIComponent(item.href).includes(page), id);
  }
  assert.match(links.x.href, /^https:\/\/twitter\.com\/intent\/tweet\?text=I%20matched%203%20of%2012/);
  assert.match(links.email.link, /utm_medium=email/);
  assert.match(links.whatsapp.link, /utm_medium=social/);
});

test('withUtm keeps an existing query and the fragment', () => {
  assert.equal(L.withUtm('https://a.b/c', { utm_source: 'x' }), 'https://a.b/c?utm_source=x');
  assert.equal(L.withUtm('https://a.b/c?d=1#top', { utm_source: 'x y' }), 'https://a.b/c?d=1&utm_source=x%20y#top');
});

test('share texts fit a post and never use dashes', () => {
  const texts = [L.shareText('page'), L.shareText('dare'), L.shareText('stat', 'A finding.'), L.offer(L.CONFIG)];
  for (let k = 0; k <= 12; k++) texts.push(L.shareText('result', k), L.verdict(k).headline, L.verdict(k).detail);
  for (const t of texts) {
    assert.ok(!/[–—]/.test(t), t);
    assert.ok(t.length <= 280 - 24, `${t.length} chars: ${t}`);   // X counts any link as 23 + a space
  }
  assert.match(L.shareText('result', 7), /beats all 152 astrologers/);
  assert.match(L.shareText('result', 2), /averaged 2\.49 and the best got 5/);
});

test('chart wheels are deterministic per seed', () => {
  const a = L.wheelSVG(7), b = L.wheelSVG(7), c = L.wheelSVG(8);
  assert.equal(a, b);
  assert.notEqual(a, c);
  assert.ok(a.startsWith('<svg') && a.endsWith('</svg>'));
  assert.ok(!L.wheelSVG(7, { glyphs: false }).includes('<text'));
  assert.ok(!a.includes('NaN'));
});
