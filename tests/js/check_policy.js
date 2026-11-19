/* Run site/policy.js on tests/vectors/policy.json and compare with what engine/policy.py decided, under the default
   policy and every single-rule change.

     node tests/js/check_policy.js

   Exits 1 on any disagreement, printing the first few. */
"use strict";
const fs = require("fs");
const path = require("path");
const here = path.resolve(__dirname, "..", "..");
const P = require(path.join(here, "site", "policy.js"));
const v = JSON.parse(fs.readFileSync(path.join(here, "tests", "vectors", "policy.json"), "utf8"));

function applied(policy, variant) {
  const p = JSON.parse(JSON.stringify(policy));
  p.rules.forEach((r) => { if (r.id === variant.rule) { r.verdict = variant.verdict; } });
  return p;
}

let checked = 0;
const bad = [];
for (const variant of v.variants) {
  const policy = applied(v.policy, variant);
  v.facts.forEach((facts, i) => {
    const got = P.decide(facts, policy), want = variant.expect[i];
    checked += 1;
    if (got.verdict !== want.verdict || got.rule !== want.rule || got.stop !== want.stop) {
      bad.push(`${variant.name}: ${JSON.stringify(facts)} gave ${JSON.stringify(got)}, Python ${JSON.stringify(want)}`);
    }
  });
}
bad.slice(0, 5).forEach((line) => console.log("FAIL " + line));
console.log(`${checked - bad.length} of ${checked} policy decisions agree`);
process.exit(bad.length ? 1 : 0);
