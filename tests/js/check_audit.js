/* Run site/audit.js on tests/vectors/audit.json: the SHA-256 cases, every entry's canonical JSON and hash, every
   chain's verify result, and an entry appended in the browser, all against what engine/audit.py produced.

     node tests/js/check_audit.js

   Exits 1 on any disagreement. */
"use strict";
const fs = require("fs");
const path = require("path");
const here = path.resolve(__dirname, "..", "..");
const A = require(path.join(here, "site", "audit.js"));
const v = JSON.parse(fs.readFileSync(path.join(here, "tests", "vectors", "audit.json"), "utf8"));

const bad = [];
let checked = 0;
function expect(name, got, want) {
  checked += 1;
  if (JSON.stringify(got) !== JSON.stringify(want)) { bad.push(`${name}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`); }
}

v.sha256.forEach((c, i) => expect(`sha256 case ${i}`, A.sha256(c.text), c.hash));
v.entries.forEach((c, i) => {
  expect(`canonical ${i}`, A.canonical(c.entry), c.canonical);
  expect(`hash ${i}`, A.entryHash(c.entry), c.hash);
});
v.chains.forEach((c) => expect(`verify, ${c.name}`, A.verify(c.entries, c.head || null), c.expect));
const after = A.append(v.append.base, v.append.fields);
expect("an entry appended in the browser", after[after.length - 1].hash, v.append.hash);
expect("the appended chain verifies", A.verify(after, null).ok, true);

bad.slice(0, 5).forEach((line) => console.log("FAIL " + line));
console.log(`${checked - bad.length} of ${checked} audit checks agree`);
process.exit(bad.length ? 1 : 0);
