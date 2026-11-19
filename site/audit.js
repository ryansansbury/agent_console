/* The audit log's check in the visitor's browser: the same canonical JSON and SHA-256 chain engine/audit.py writes,
   so verify fails at the same entry for the same change. It carries its own small SHA-256, so the page and the node
   tests run the same synchronous code however the browser opened the page. tests/js/check_audit.js runs it on every
   vector engine/audit.py wrote. A classic script with no dependencies. */
(function (root) {
  "use strict";
  var GENESIS = "0000000000000000000000000000000000000000000000000000000000000000";
  var K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];

  function utf8(text) {
    var out = [];
    for (var i = 0; i < text.length; i++) {
      var c = text.codePointAt(i);
      if (c > 0xffff) { i++; }
      if (c < 0x80) { out.push(c); }
      else if (c < 0x800) { out.push(0xc0 | (c >> 6), 0x80 | (c & 63)); }
      else if (c < 0x10000) { out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63)); }
      else { out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63)); }
    }
    return out;
  }

  function sha256(text) {
    var bytes = utf8(text), n = bytes.length;
    var h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
    bytes.push(0x80);
    while (bytes.length % 64 !== 56) { bytes.push(0); }
    var bits = n * 8;
    for (var s = 7; s >= 0; s--) { bytes.push(s >= 4 ? Math.floor(bits / Math.pow(2, 8 * s)) & 255 : (bits >>> (8 * s)) & 255); }
    var w = new Array(64);
    for (var off = 0; off < bytes.length; off += 64) {
      for (var t = 0; t < 16; t++) {
        w[t] = (bytes[off + 4 * t] << 24) | (bytes[off + 4 * t + 1] << 16) | (bytes[off + 4 * t + 2] << 8) | bytes[off + 4 * t + 3];
      }
      for (t = 16; t < 64; t++) {
        var x = w[t - 15], y = w[t - 2];
        var s0 = ((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3);
        var s1 = ((y >>> 17) | (y << 15)) ^ ((y >>> 19) | (y << 13)) ^ (y >>> 10);
        w[t] = (w[t - 16] + s0 + w[t - 7] + s1) | 0;
      }
      var a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], k = h[7];
      for (t = 0; t < 64; t++) {
        var S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
        var ch = (e & f) ^ (~e & g);
        var t1 = (k + S1 + ch + K[t] + w[t]) | 0;
        var S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
        var mj = (a & b) ^ (a & c) ^ (b & c);
        var t2 = (S0 + mj) | 0;
        k = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
      }
      h[0] = (h[0] + a) | 0; h[1] = (h[1] + b) | 0; h[2] = (h[2] + c) | 0; h[3] = (h[3] + d) | 0;
      h[4] = (h[4] + e) | 0; h[5] = (h[5] + f) | 0; h[6] = (h[6] + g) | 0; h[7] = (h[7] + k) | 0;
    }
    return h.map(function (v) { return ("00000000" + (v >>> 0).toString(16)).slice(-8); }).join("");
  }

  function canonical(entry) {
    var keys = Object.keys(entry).filter(function (k) { return k !== "hash"; }).sort();
    var body = {};
    keys.forEach(function (k) {
      var v = entry[k];
      if (typeof v === "string") { v = v.normalize("NFC"); }
      else if (typeof v !== "number" || Math.floor(v) !== v) { throw new TypeError("an audit entry holds only text and whole numbers"); }
      body[k] = v;
    });
    return JSON.stringify(body);
  }

  function entryHash(entry) { return sha256(entry.prev + "\n" + canonical(entry)); }

  function verify(entries, head) {
    for (var i = 0; i < entries.length; i++) {
      var e = entries[i];
      if (e.seq !== i + 1) { return {ok: false, count: entries.length, failed_at: e.seq, why: "sequence"}; }
      if (e.prev !== (i ? entries[i - 1].hash : GENESIS)) { return {ok: false, count: entries.length, failed_at: e.seq, why: "link"}; }
      var good;
      try { good = entryHash(e) === e.hash; } catch (err) { good = false; }
      if (!good) { return {ok: false, count: entries.length, failed_at: e.seq, why: "content"}; }
    }
    if (head && entries.length && entries[entries.length - 1].hash !== head) {
      return {ok: false, count: entries.length, failed_at: entries[entries.length - 1].seq, why: "head"};
    }
    return {ok: true, count: entries.length, failed_at: null, why: null};
  }

  /* An entry added in the browser, like the visitor's answer to the waiting push, chained the same way. */
  function append(entries, fields) {
    var entry = {}, names = ["at", "session", "actor", "action", "target", "verdict", "rule", "result"];
    names.forEach(function (k) { entry[k] = fields[k] === undefined ? "" : fields[k]; });
    entry.seq = entries.length + 1;
    entry.prev = entries.length ? entries[entries.length - 1].hash : GENESIS;
    entry.hash = entryHash(entry);
    return entries.concat([entry]);
  }

  var api = {sha256: sha256, canonical: canonical, entryHash: entryHash, verify: verify, append: append, GENESIS: GENESIS};
  if (typeof module !== "undefined" && module.exports) { module.exports = api; } else { root.ACAudit = api; }
})(this);
