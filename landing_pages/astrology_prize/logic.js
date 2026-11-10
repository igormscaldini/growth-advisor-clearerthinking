/* Astrology prize landing page: numbers, odds, share links and the chart-wheel drawing.
   Loaded by index.html and og_card.html (window.PrizeLogic) and by Node for logic.test.js.
   CONFIG and STUDY_2024 are the single source for every figure the page computes; the static copy in
   index.html is checked against them by tests/test_astrology_prize_lp.py. */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PrizeLogic = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var CONFIG = {
    prize: 10000,       // US dollars
    questions: 12,      // people to match per round
    bar: 11,            // correct matches needed, in each round
    options: 5,         // charts shown per person (1 real + 4 decoys)
    campaign: 'astrology_prize'
  };

  // Clearer Thinking's 2024 study (n = 152 astrologers). Source: the results table in the study report,
  // https://www.clearerthinking.org/post/can-astrologers-use-astrological-charts-to-understand-people-s-character-and-lives-our-new-study-pu
  var STUDY_2024 = {
    astrologers: 152,
    meanScore: 2.49,
    bestScore: 5,
    prize: 1000,
    // % of astrologers who matched 0, 1, 2 ... 12 charts
    scorePct: [5.3, 20.4, 23.0, 28.3, 17.1, 5.9, 0, 0, 0, 0, 0, 0, 0]
  };

  /* ---------- odds ---------- */

  function choose(n, k) {
    if (k < 0 || k > n) return 0;
    k = Math.min(k, n - k);
    var c = 1;
    for (var i = 1; i <= k; i++) c = c * (n - k + i) / i;
    return c;
  }

  function binomPmf(n, k, p) {
    return choose(n, k) * Math.pow(p, k) * Math.pow(1 - p, n - k);
  }

  // P(X >= k) for X ~ Binomial(n, p)
  function binomTail(n, k, p) {
    var total = 0;
    for (var i = Math.max(k, 0); i <= n; i++) total += binomPmf(n, i, p);
    return total;
  }

  // % of blind guessers expected at each score 0..n
  function chancePct(n, p) {
    var out = [];
    for (var k = 0; k <= n; k++) out.push(100 * binomPmf(n, k, p));
    return out;
  }

  function chanceMean(cfg) {
    cfg = cfg || CONFIG;
    return cfg.questions / cfg.options;
  }

  // Probability of reaching the bar in ONE round by guessing blind.
  function luckyWinProbability(cfg) {
    cfg = cfg || CONFIG;
    return binomTail(cfg.questions, cfg.bar, 1 / cfg.options);
  }

  // "5 million" for a probability of 1 in 4,982,000. One significant figure from a million up, two below.
  function oneInText(prob) {
    var n = 1 / prob;
    if (n >= 1e9) return Number((n / 1e9).toPrecision(1)) + ' billion';
    if (n >= 1e6) return Number((n / 1e6).toPrecision(1)) + ' million';
    if (n >= 100) return Number(n.toPrecision(2)).toLocaleString('en-US');
    return String(Math.round(n));
  }

  function formatMoney(n) {
    return '$' + Math.round(n).toLocaleString('en-US');
  }

  function formatPct(v) {
    if (v === 0) return '0%';
    if (v < 0.1) return 'under 0.1%';
    return v.toFixed(1) + '%';
  }

  /* ---------- seeded randomness for the decorative wheels ---------- */

  // Small seeded generator, so wheels and tests are reproducible.
  function mulberry32(seed) {
    var a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      var t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* ---------- sharing ---------- */

  function offer(cfg) {
    return formatMoney(cfg.prize) + ' for the first astrologer who can match ' + cfg.bar + ' of ' + cfg.questions +
      ' strangers to their birth charts.';
  }

  // kind: 'page' (anyone), 'dare' (sent to an astrologer), 'stat' (one finding)
  function shareText(kind, value, cfg, study) {
    cfg = cfg || CONFIG;
    study = study || STUDY_2024;
    var ask = formatMoney(cfg.prize) + ' to any astrologer who can get ' + cfg.bar + ':';
    if (kind === 'dare') {
      return 'You read birth charts, so this is for you: Clearer Thinking will pay ' + formatMoney(cfg.prize) +
        ' to the first astrologer who can match ' + cfg.bar + ' of ' + cfg.questions +
        ' people to their charts. Free to enter:';
    }
    if (kind === 'stat') {
      return value + ' Now there is ' + ask;
    }
    return offer(cfg) + ' In 2024, ' + study.astrologers + ' astrologers took a version of this test. The best score was ' +
      study.bestScore + '.';
  }

  function withUtm(url, params) {
    var hash = '';
    var at = url.indexOf('#');
    if (at !== -1) { hash = url.slice(at); url = url.slice(0, at); }
    var parts = [];
    for (var key in params) {
      if (Object.prototype.hasOwnProperty.call(params, key)) {
        parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(params[key]));
      }
    }
    return url + (url.indexOf('?') === -1 ? '?' : '&') + parts.join('&') + hash;
  }

  var NETWORKS = [
    { id: 'x', label: 'X', medium: 'social' },
    { id: 'whatsapp', label: 'WhatsApp', medium: 'social' },
    { id: 'facebook', label: 'Facebook', medium: 'social' },
    { id: 'reddit', label: 'Reddit', medium: 'social' },
    { id: 'bluesky', label: 'Bluesky', medium: 'social' },
    { id: 'linkedin', label: 'LinkedIn', medium: 'social' },
    { id: 'email', label: 'Email', medium: 'email' }
  ];

  // The page link as it should travel on one network, tagged so GA4 can tell the shares apart.
  function taggedUrl(pageUrl, source, medium, content, cfg) {
    cfg = cfg || CONFIG;
    return withUtm(pageUrl, { utm_source: source, utm_medium: medium, utm_campaign: cfg.campaign, utm_content: content });
  }

  function shareLinks(pageUrl, text, content, cfg) {
    cfg = cfg || CONFIG;
    var e = encodeURIComponent;
    var out = {};
    NETWORKS.forEach(function (net) {
      var link = taggedUrl(pageUrl, net.id, net.medium, content, cfg);
      var href;
      if (net.id === 'x') href = 'https://twitter.com/intent/tweet?text=' + e(text) + '&url=' + e(link);
      else if (net.id === 'whatsapp') href = 'https://wa.me/?text=' + e(text + ' ' + link);
      else if (net.id === 'facebook') href = 'https://www.facebook.com/sharer/sharer.php?u=' + e(link);
      else if (net.id === 'reddit') href = 'https://www.reddit.com/submit?url=' + e(link) + '&title=' + e(offer(cfg));
      else if (net.id === 'bluesky') href = 'https://bsky.app/intent/compose?text=' + e(text + ' ' + link);
      else if (net.id === 'linkedin') href = 'https://www.linkedin.com/sharing/share-offsite/?url=' + e(link);
      else href = 'mailto:?subject=' + e(formatMoney(cfg.prize) + ' astrology prize') + '&body=' + e(text + '\n\n' + link);
      out[net.id] = { label: net.label, href: href, link: link };
    });
    return out;
  }

  /* ---------- chart wheel (decorative, generated; not a real person's chart) ---------- */

  var SIGNS = '\u2648\u2649\u264A\u264B\u264C\u264D\u264E\u264F\u2650\u2651\u2652\u2653';
  var PLANETS = '\u2609\u263D\u263F\u2640\u2642\u2643\u2644\u2645\u2646\u2647';
  var TEXT_STYLE = '\uFE0E';   // asks for the text glyph, not the emoji
  var GLYPH_FONT = "'Apple Symbols','Segoe UI Symbol','Noto Sans Symbols2','Noto Sans Symbols','DejaVu Sans',sans-serif";

  function wheelSVG(seed, opts) {
    var o = opts || {};
    var glyphs = o.glyphs !== false;
    var soft = o.soft || '#0885f8';   // CT main blue
    var hard = o.hard || '#f8911b';   // CT orange
    var count = o.planets || (glyphs ? 10 : 7);
    var rand = mulberry32(seed);
    var C = 100, R1 = 97, R2 = glyphs ? 81 : 87, R3 = glyphs ? 60 : 64;
    var asc = rand() * 360;

    function pt(r, deg) {
      var a = deg * Math.PI / 180;
      return [(C + r * Math.cos(a)).toFixed(2), (C - r * Math.sin(a)).toFixed(2)];
    }
    function seg(a, b, opacity, width, colour) {
      return '<line x1="' + a[0] + '" y1="' + a[1] + '" x2="' + b[0] + '" y2="' + b[1] + '" stroke="' +
        (colour || 'currentColor') + '" stroke-width="' + width + '" opacity="' + opacity + '" stroke-linecap="round"/>';
    }
    function ring(r, opacity, width) {
      return '<circle cx="' + C + '" cy="' + C + '" r="' + r + '" fill="none" stroke="currentColor" stroke-width="' +
        width + '" opacity="' + opacity + '"/>';
    }
    function glyph(ch, p, size, opacity) {
      return '<text x="' + p[0] + '" y="' + p[1] + '" font-size="' + size + '" font-family="' + GLYPH_FONT +
        '" text-anchor="middle" dominant-baseline="central" fill="currentColor" opacity="' + opacity + '">' +
        ch + TEXT_STYLE + '</text>';
    }

    var s = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" aria-hidden="true" focusable="false">';
    s += ring(R1, 0.9, 0.7) + ring(R2, 0.75, 0.5) + ring(R3, 0.6, 0.5);

    var i, d;
    for (i = 0; i < 12; i++) {
      s += seg(pt(R2, asc + i * 30), pt(R1, asc + i * 30), 0.75, 0.5);
      if (glyphs) s += glyph(SIGNS.charAt(i), pt((R1 + R2) / 2, asc + i * 30 + 15), 9, 0.9);
    }
    for (d = 0; d < 360; d += (glyphs ? 5 : 10)) {
      s += seg(pt(R2 - (d % 10 === 0 ? 3.5 : 2), asc + d), pt(R2, asc + d), 0.5, 0.35);
    }

    // twelve unequal houses, as in a quadrant house system
    var widths = [], total = 0;
    for (i = 0; i < 12; i++) { widths.push(22 + rand() * 16); total += widths[i]; }
    var cusp = asc;
    for (i = 0; i < 12; i++) {
      var axis = i % 3 === 0;
      s += seg(pt(axis ? 6 : R3 * 0.45, cusp), pt(R2, cusp), axis ? 0.75 : 0.3, axis ? 0.7 : 0.4);
      cusp += widths[i] * 360 / total;
    }

    var degs = [];
    for (i = 0; i < count; i++) degs.push(rand() * 360);
    for (i = 0; i < count; i++) {
      for (var j = i + 1; j < count; j++) {
        var diff = Math.abs(degs[i] - degs[j]) % 360;
        if (diff > 180) diff = 360 - diff;
        var isSoft = Math.abs(diff - 60) < 7 || Math.abs(diff - 120) < 7;
        var isHard = Math.abs(diff - 90) < 7 || diff > 173;
        if (isSoft || isHard) s += seg(pt(R3, degs[i]), pt(R3, degs[j]), 0.7, 0.55, isSoft ? soft : hard);
      }
    }
    for (i = 0; i < count; i++) {
      var p = pt(R3, degs[i]);
      s += '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="1.5" fill="currentColor"/>';
      if (glyphs) s += glyph(PLANETS.charAt(i % PLANETS.length), pt((R2 + R3) / 2, degs[i]), 8, 0.85);
    }
    s += '<circle cx="' + C + '" cy="' + C + '" r="2" fill="currentColor"/></svg>';
    return s;
  }

  return {
    CONFIG: CONFIG,
    STUDY_2024: STUDY_2024,
    NETWORKS: NETWORKS,
    choose: choose,
    binomPmf: binomPmf,
    binomTail: binomTail,
    chancePct: chancePct,
    chanceMean: chanceMean,
    luckyWinProbability: luckyWinProbability,
    oneInText: oneInText,
    formatMoney: formatMoney,
    formatPct: formatPct,
    mulberry32: mulberry32,
    offer: offer,
    shareText: shareText,
    withUtm: withUtm,
    taggedUrl: taggedUrl,
    shareLinks: shareLinks,
    wheelSVG: wheelSVG
  };
});
