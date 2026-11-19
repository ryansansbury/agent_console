/* The node click-through. It runs the built page's own scripts against a small DOM (dom.js): it opens on the trace
   with the quarantine selected, selects every tile, walks the counts and the inspector's steps, answers the waiting
   push and checks the chain still verifies, replays the morning with its clock and counts running, opens every
   session and its outputs, replays a terminal, changes rules and reads the simulator's sentences, runs the audit log's
   tamper steps, opens How it works and the code view, walks the tour, and moves along the tiles with the arrow keys.
   Exits 1 on any failed check.

       node tests/js/check_app.js [site folder]

   It can't see layout, color, motion or real timing. owner/browser_check.py covers those in real Chrome. */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const {Document} = require("./dom.js");

const SITE = path.resolve(process.argv[2] || path.join(__dirname, "..", "..", "site"));
const checks = [], errors = [];
function check(name, ok, detail) { checks.push({name, ok: !!ok, detail: detail === undefined ? "" : String(detail).slice(0, 300)}); }

const html = fs.readFileSync(path.join(SITE, "index.html"), "utf8");
const doc = new Document(html);
check("index.html parses with every tag closed", doc.errors.length === 0, doc.errors.slice(0, 3).join("; "));
// The canonical link names the live address and loads nothing, so it's the one link allowed to.
check("nothing is loaded from another site", !/<(?:script|img|link|audio|video|iframe)[^>]+(?:src|href)=['"](?:https?:)?\/\//.test(html.replace(/<link rel='canonical' href='[^']+'>/, "")));
check("no inline script or style", !/<script>[^<]|<script[^>]*>[^<]+<\/script>| style=/.test(html));
const timers = [];
const win = {document: doc, innerWidth: 1600, innerHeight: 1000, addEventListener() {}, devicePixelRatio: 1,
  setTimeout(fn) { timers.push(fn); return timers.length; }, clearTimeout(id) { if (id) { timers[id - 1] = null; } },
  location: {hash: "", protocol: "file:"}, history: {replaceState(s, t, url) { win.location.hash = url; }},
  scrollX: 0, scrollY: 0};
win.window = win;
const ctx = vm.createContext(win);
for (const name of ["data.js", "policy.js", "audit.js", "code.js", "app.js"]) {
  try { vm.runInContext(fs.readFileSync(path.join(SITE, name), "utf8"), ctx, {filename: name}); }
  catch (e) { errors.push(name + " threw: " + (e && e.stack || e)); }
}
function flush(limit) {
  for (let guard = 0; guard < (limit || 400) && timers.some(Boolean); guard++) {
    const i = timers.findIndex(Boolean), fn = timers[i];
    timers[i] = null;
    fn();
  }
}
const AC = win.AC, ACP = win.ACP, $ = (s) => doc.querySelector(s), $$ = (s) => doc.querySelectorAll(s);
const click = (el) => { doc.dispatch("click", el); flush(); };
const key = (el, k) => { doc.dispatch("keydown", el, {key: k}); flush(); };
const text = (s) => (($(s) || {}).textContent || "");
function attempt(name, fn) { try { fn(); } catch (e) { errors.push(name + ": " + (e && e.stack || e)); } }
const U = (AC && AC.ui) || {};
const lanes = () => AC.mornings[ACP.state().model].lanes;
const lane = (job) => lanes().filter((l) => l.job === job)[0];

if (AC && ACP) {
  attempt("opening", () => {
    flush();
    const st = ACP.state(), sel = st.sel.split(":");
    const ev = lane(sel[0]).events.filter((e) => String(e.seq) === sel[1])[0];
    check("the page opens on the trace", st.view === "trace" && !$("#v-trace").hidden && $("#v-how").hidden);
    check("a fresh load selects the quarantine", ev && ev.kind === "cut" && sel[0] === "pricing-research", st.sel);
    check("there are four lanes with labels", $$(".lane").length === 4 && $$(".lab").length === 4);
    check("the title names the day and the clock", /\d+:\d\d (AM|PM) to \d+:\d\d (AM|PM)/.test(text("#t-title")), text("#t-title"));
    check("the counts name the calls and the spend", $$(".kpis .kpi").length === 7 && /tool calls/.test(text(".kpis")) && /\$/.test(text(".kpis")),
      text(".kpis"));
    const calls = lanes().reduce((n, l) => n + l.events.filter((e) => e.kind === "call").length, 0);
    const turns = lanes().reduce((n, l) => n + l.events.filter((e) => e.kind === "model").length, 0);
    check("the calls count matches the recording", text("[data-kpi='calls']") === String(calls), text("[data-kpi='calls']"));
    check("every allowed call shows its tool's icon", $$(".tk").length > 8 && $$(".tk").every((el) => el.querySelectorAll("svg path, svg circle").length > 0));
    check("every model turn sits on its lane", $$(".seq .turn[data-turn]").length === turns, `${$$(".seq .turn[data-turn]").length} of ${turns}`);
    check("each lane ends with its cost", lanes().every((l) => /\$/.test(text(`[data-cost='${l.job}']`))));
    const said = $("#q-said"), given = $("#q-given");
    check("what the page said holds the planted note, struck", said && $$("#q-said .inj").length >= 1 &&
      /ignore your previous instructions/.test(said.textContent));
    check("what the agent was given holds the cut and not the note", given && $$("#q-given .cut").length >= 1 &&
      !/ignore your previous instructions/.test(given.textContent) && given.textContent.indexOf(AC.outside_domain) < 0);
    check("a thread runs from the cut sentence to its marker", $$("#detail .threads path").length === 1 && $$("#detail .threads circle").length === 2);
    check("the selected event names its audit entry", /Audit entry #\d+/.test(text("#detail")), text("#detail").slice(0, 120));
    check("the model picker lists every model", $$("#model option").length === AC.models.length);
  });
  attempt("every mark and tick", () => {
    const all = $$(".mk, .tk");
    let ok = 0;
    all.forEach((el) => {
      click(el);
      if (ACP.state().sel === el.getAttribute("data-ev") && text("#detail").length > 40 && el.classList.contains("sel")) { ok += 1; }
    });
    check("every mark and tick opens its detail", ok === all.length && all.length > 8, `${ok} of ${all.length}`);
    check("every mark has a label for screen readers", all.every((el) => (el.getAttribute("aria-label") || "").length > 10));
    check("the address follows the selection", /^#trace\/[\w-]+:\d+$/.test(win.location.hash), win.location.hash);
  });
  attempt("the counts and the inspector's steps", () => {
    click($("[data-pick='deny']"));
    const first = ACP.state().sel, denied = (k) => !!$(`.mk.deny[data-ev='${k}'], .mk.stop[data-ev='${k}'], .mk.refused[data-ev='${k}']`);
    check("a count selects a tile it counts", denied(first), first);
    click($("[data-pick='deny']"));
    check("pressing it again moves to the next one", denied(ACP.state().sel) && ACP.state().sel !== first, ACP.state().sel);
    click($("[data-pick='quarantine']"));
    check("the quarantine count opens the quarantine", text("#detail").indexOf(U.q_said) >= 0);
    const here = ACP.state().sel;
    click($("#detail [data-step='1']"));
    const ahead = ACP.state().sel;
    check("the inspector's next step moves on", ahead !== here && /Audit entry #\d+/.test(text("#detail")), ahead);
    click($("#detail [data-step='-1']"));
    check("its previous step comes back", ACP.state().sel === here, ACP.state().sel);
    click($$(".tk")[0]);
    check("the first event can't step back", $("#detail [data-step='-1']").hasAttribute("disabled"));
  });
  attempt("the denial and the push", () => {
    const stop = $(".mk.stop");
    check("the secrets denial shows as a stop", !!stop);
    if (stop) {
      click(stop);
      check("its detail says the session ended", text("#detail").indexOf(U.deny_stop.slice(0, 40)) >= 0, text("#detail").slice(0, 200));
      check("its detail names the rule", /Secrets files/.test(text("#detail")));
    }
    const wait = $(".mk.wait");
    check("the push shows as waiting", !!wait);
    if (wait) {
      click(wait);
      const before = ACP.state().chain;
      check("the waiting push offers approve and deny", $$("#detail [data-answer]").length === 2);
      click($("#detail [data-answer='approve']"));
      check("approving adds an entry to the chain", ACP.state().chain === before + 1 && ACP.state().answers["billing-export"] === "approve");
      check("the chain still verifies with the answer in it", ACP.verify().ok, JSON.stringify(ACP.verify()));
      check("the detail says what the approval means", text("#detail").indexOf(U.you_approved.slice(0, 30)) >= 0);
      check("the lane says it was approved", text(".lab[data-lane='billing-export']").indexOf(U.lane_answer.approve) >= 0);
    }
  });
  attempt("the replay", () => {
    doc.dispatch("click", $("#replay"));
    for (let i = 0; i < 40; i++) { const j = timers.findIndex(Boolean); if (j < 0) { break; } const fn = timers[j]; timers[j] = null; fn(); }
    const hidden = $$("#v-trace .later").length;
    check("mid-replay some marks are still to come", ACP.state().replaying && hidden > 0, hidden);
    check("mid-replay the clock runs", /^\d+:\d\d:\d\d (AM|PM)$/.test(text("#t-clock")) && $("#trace").classList.contains("replaying"), text("#t-clock"));
    const calls = lanes().reduce((n, l) => n + l.events.filter((e) => e.kind === "call").length, 0);
    check("mid-replay the counts are partway", Number(text("[data-kpi='calls']")) < calls, text("[data-kpi='calls']"));
    flush(5000);
    check("the replay ends with everything drawn and the quarantine selected", !ACP.state().replaying && $$("#v-trace .later").length === 0 &&
      ACP.state().sel.indexOf("pricing-research:") === 0, ACP.state().sel);
  });
  attempt("the sessions", () => {
    click($(".lab[data-lane='infra-scripts']"));
    check("a lane's label opens its session", ACP.state().view === "session" && ACP.state().job === "infra-scripts");
    let ok = 0;
    for (const l of lanes()) {
      click($(`[data-session='${l.job}']`));
      if ($$("#tbody .prompt").length === 1 && $("#tbody").children.length === ACP.terminal() && text(".thead").indexOf(l.job) >= 0) { ok += 1; }
    }
    check("every session renders as a terminal", ok === lanes().length, `${ok} of ${lanes().length}`);
    click($("[data-session='billing-export']"));
    check("the push pauses the billing terminal", $$("#tbody .pause").length === 1);
    const toggle = $("#tbody .toggle");
    if (toggle) {
      click(toggle);
      check("a call's output opens", $$("#tbody .tout").length === 1);
    }
    click($("#replay"));
    flush(5000);
    check("a terminal replay ends with every line shown", $("#tbody").children.length === ACP.terminal());
    check("the address names the session", win.location.hash === "#session/billing-export", win.location.hash);
  });
  attempt("the policy and the simulator", () => {
    click($("[data-view='policies']"));
    check("the policy lists every rule", $$("#rules .rule").length === AC.policy.rules.length);
    check("it opens with nothing changed", text("#sim").indexOf(U.sim_same) >= 0, text("#sim"));
    click($("[data-rule='push'][data-verdict='allow']"));
    const pushes = lanes().reduce((n, l) => n + l.events.filter((e) => e.kind === "call" && e.rule === "push").length, 0);
    check("allowing pushes changes each recorded push", ACP.simulate({push: "allow"}).changes === pushes && pushes > 0, pushes);
    check("the sentence says what changed", /would run without asking anyone/.test(text("#sim")), text("#sim"));
    check("the changed rule is marked", $$(".rule.changed").length === 1);
    click($("[data-rule='secrets'][data-verdict='allow']"));
    check("allowing the secrets file changes its call", /would run/.test(text("#sim")) && ACP.simulate({secrets: "allow"}).changes >= 1);
    click($("[data-rule='tests'][data-verdict='deny']"));
    click($("[data-poljob='parser-lib']"));
    check("denying the tests marks the calls after them", $$(".calls tr.dim").length > 0 && $$(".calls tr.chg").length > 0);
    click($("#reset-policy"));
    check("reset puts the recorded policy back", text("#sim").indexOf(U.sim_same) >= 0 && $$(".rule.changed").length === 0);
    check("an address the recording never used changes nothing", ACP.simulate({"other-hosts": "allow"}).changes === 0);
  });
  attempt("the audit log", () => {
    click($("[data-view='audit']"));
    const rows = $$(".ledger tbody tr").length;
    check("the log lists every entry", rows === ACP.state().chain && rows > 10, rows);
    click($("[data-audit='verify']"));
    check("the chain verifies", $$(".result.ok").length === 1);
    click($("[data-audit='1']"));
    const r1 = ACP.verify();
    check("changing an old entry fails at that entry", !r1.ok && r1.why === "content" && $$(".ledger tr.bad").length === 1, JSON.stringify(r1));
    click($("[data-audit='2']"));
    const r2 = ACP.verify();
    check("fixing its hash fails at the next link", !r2.ok && r2.why === "link" && r2.failed_at === r1.failed_at + 1, JSON.stringify(r2));
    click($("[data-audit='3']"));
    const r3 = ACP.verify();
    check("rewriting everything after fails at the published head", !r3.ok && r3.why === "head", JSON.stringify(r3));
    click($("[data-audit='reset']"));
    check("putting it back verifies again, with the visitor's answer kept", ACP.verify().ok && ACP.state().chain === rows);
  });
  attempt("how it works", () => {
    click($("[data-view='how']"));
    check("How it works opens", !$("#v-how").hidden && $("#v-trace").hidden);
    check("it carries the map, the layers and the recorded sessions", $$("#v-how table.map tr").length >= 7 && $$("#v-how ol li").length >= 10 &&
      $$("#v-how table.grid").length >= 2);
    check("the code view lists the files", $$("#code-tree button").length > 20);
    click($$(".cfeat")[1]);
    check("a featured file opens", text("#code-path") === "engine/reader.py" && text("#code-body").indexOf("def read_page") >= 0);
  });
  attempt("the brand goes home", () => {
    click($("[data-view='audit']"));
    click($$(".tk")[0] || $("[data-view='trace']"));
    click($("[data-view='policies']"));
    const ev = doc.dispatch("click", $(".brand[data-home]"));
    flush();
    const st = ACP.state(), sel = String(st.sel).split(":"), e = lane(sel[0]).events.filter((x) => String(x.seq) === sel[1])[0];
    check("the brand opens the morning", st.view === "trace" && !$("#v-trace").hidden && $("#v-policies").hidden, st.view);
    check("it selects the event a fresh load opens on", e && e.kind === "cut", st.sel);
    check("it stays on the page", ev.defaultPrevented && win.location.hash.indexOf("#trace") === 0, win.location.hash);
  });
  attempt("the tour", () => {
    click($("#tour-start"));
    let ok = 0;
    for (let n = 1; n <= ACP.steps; n++) {
      if (ACP.state().tour === n && !$("#tour-box").hidden && text("#tour-box").length > 40 && !$("#tour").hidden) { ok += 1; }
      if (n === 2 && ACP.state().sel.indexOf("pricing-research:") !== 0) { ok -= 1; }
      if (n === 4) { const st = ACP.state().sel; if (!$(`.mk.stop[data-ev='${st}']`)) { ok -= 1; } }
      if (n === 6 && ACP.state().view !== "session") { ok -= 1; }
      click($("[data-tour='next']"));
    }
    check("every tour step shows its text in the right place", ok === ACP.steps, `${ok} of ${ACP.steps}`);
    check("the tour closes after its last step", ACP.state().tour === 0 && $("#tour-box").hidden);
  });
  attempt("keyboard paths", () => {
    click($("[data-view='trace']"));
    const first = $(".lane[data-job='parser-lib'] .tk");
    click(first);
    key(first, "ArrowRight");
    check("the right arrow moves along the lane", ACP.state().sel !== first.getAttribute("data-ev") && ACP.state().sel.indexOf("parser-lib:") === 0);
    const here = $(`[data-ev='${ACP.state().sel}']`);
    key(here, "ArrowDown");
    check("the down arrow moves to the next lane", ACP.state().sel.indexOf("billing-export:") === 0, ACP.state().sel);
  });
}

const failed = checks.filter((c) => !c.ok);
failed.forEach((c) => console.log(`FAIL ${c.name} ${c.detail}`));
errors.forEach((e) => console.log(`ERROR ${e}`));
console.log(`${checks.length - failed.length} of ${checks.length} page checks pass`);
process.exit(failed.length || errors.length ? 1 : 0);
