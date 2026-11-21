/* Agent Console. The page script: the morning as four lanes of tiles, one per tool call, with the selected event in the
   inspector below, a session as a terminal, the policy with its simulator, and the audit log with its tamper test. Everything comes from window.AC,
   which the build wrote, so the page reaches nothing on the network. The policy decides in your browser through
   site/policy.js and the chain checks through site/audit.js, the same logic the build ran, proven by the parity
   vectors. Events are handled once at the document, positions go through the CSSOM and never into inline styles, and
   pure helpers sit on window.ACP for the node check. */
(function () {
  "use strict";
  var win = window, doc = document, AC = win.AC || {}, U = AC.ui || {}, Pol = win.ACPolicy, Aud = win.ACAudit;
  var ACP = win.ACP = {};
  var VIEWS = ["trace", "session", "policies", "audit", "how"], SCREENS = VIEWS;
  var CUT_MARK = "[cut: text addressed to an AI agent]";
  var S = {view: "trace", model: AC.route || ((AC.models || [])[0] || {}).id, sel: null, job: null, polJob: null,
    policy: null, answers: {}, chain: null, recorded: 0, tamper: 0, tamperSeq: null, result: null, replaying: false,
    t: null, tour: 0, open: {}, term: null, codeFile: null};

  /* ------------------------------------------------------------------ helpers */
  function esc(s) {
    return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"}[c];
    });
  }
  function $(sel, root) { return (root || doc).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || doc).querySelectorAll(sel)); }
  /* Words come from WORDS.md through window.AC.ui, keyed without their "ui." prefix. */
  function u(key) { return U[String(key).replace(/^ui\./, "")]; }
  function word(key, fill) {
    var s = u(key);
    if (s === undefined || s === null) { s = ""; }
    Object.keys(fill || {}).forEach(function (k) { s = String(s).split("{" + k + "}").join(fill[k]); });
    return s;
  }
  function tab(key, name) { var t = u(key) || {}; return t[name] === undefined ? name : t[name]; }
  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function money(micro) {
    if (micro > 0 && micro < 1000) { return "<$0.001"; }
    var d = (micro || 0) / 1e6;
    return "$" + (d >= 0.1 ? d.toFixed(2) : d.toFixed(3));
  }
  function short(hash) { return hash ? hash.slice(0, 4) + "…" + hash.slice(-4) : ""; }
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function calm() { return !!(win.matchMedia && win.matchMedia("(prefers-reduced-motion: reduce)").matches); }
  function phone() { return !!(win.matchMedia && win.matchMedia("(max-width: 900px)").matches); }
  function pill(cls, text) { return "<span class='pill p-" + esc(cls) + "'>" + esc(text) + "</span>"; }
  function trim(s, n) { s = String(s || ""); return s.length > n ? s.slice(0, n - 1) + "…" : s; }
  /* One icon set for the tools, the verdicts and the controls, drawn on a 24-unit grid with round strokes. */
  var DOC = "<path d='M14 3H7.5A2.5 2.5 0 0 0 5 5.5v13A2.5 2.5 0 0 0 7.5 21h9a2.5 2.5 0 0 0 2.5-2.5V8z'/><path d='M14 3v5h5'/>";
  var ICON = {
    shell: "<path d='M5 7l5 5-5 5'/><path d='M12.5 17H19'/>",
    read: DOC + "<path d='M9 13h6'/><path d='M9 17h4'/>",
    write: DOC + "<path d='M12 11v6'/><path d='M9 14h6'/>",
    edit: "<path d='M4 20l1-4.6L16.6 3.8a2.5 2.5 0 0 1 3.6 3.6L8.6 19z'/><path d='M14.5 6l3.5 3.5'/>",
    fetch: "<circle cx='12' cy='12' r='9'/><path d='M3 12h18'/><path d='M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z'/>",
    ask: "<circle cx='12' cy='8' r='3.6'/><path d='M5 20.5c.8-3.7 3.6-6.2 7-6.2s6.2 2.5 7 6.2'/>",
    deny: "<circle cx='12' cy='12' r='8.5'/><path d='M6 6l12 12'/>",
    stop: "<path d='M8.3 3h7.4L21 8.3v7.4L15.7 21H8.3L3 15.7V8.3z'/><path d='M8.5 12h7'/>",
    quarantine: "<path d='M12 3l7.5 3v5.5c0 4.6-3.2 8.3-7.5 9.5-4.3-1.2-7.5-4.9-7.5-9.5V6z'/><path d='M9 12l2.2 2.2L15.5 10'/>",
    done: "<path d='M5 12.5l4.5 4.5L19 7.5'/>",
    budget: "<path d='M12 3v18'/><path d='M16.5 7.5C15.9 6.1 14.1 5 12 5c-2.5 0-4.5 1.4-4.5 3.3 0 4.2 9 2.4 9 6.6 0 1.9-2 3.6-4.5 3.6-2.2 0-4-1.1-4.6-2.6'/>",
    rule: "<path d='M4 6h16'/><path d='M4 12h10'/><path d='M4 18h6'/><path d='M16 16l2 2 3.5-3.5'/>",
    next: "<path d='M5 12h14'/><path d='M13 6l6 6-6 6'/>",
    reply: "<path d='M5 4.5h14a2 2 0 0 1 2 2v8.5a2 2 0 0 1-2 2h-7.5L7 20.5V17H5a2 2 0 0 1-2-2V6.5a2 2 0 0 1 2-2z'/>",
    open: "<path d='M9 6l6 6-6 6'/>",
    back: "<path d='M15 6l-6 6 6 6'/>"
  };
  function icon(name, cls) {
    return "<svg class='i" + (cls ? " " + cls : "") + "' viewBox='0 0 24 24' aria-hidden='true' focusable='false'>" + (ICON[name] || ICON.shell) + "</svg>";
  }

  /* ------------------------------------------------------------------ the data */
  function morning() { return (AC.mornings || {})[S.model] || (AC.mornings || {})[Object.keys(AC.mornings || {})[0]]; }
  function lanes() { return (morning() || {}).lanes || []; }
  function lane(job) { return lanes().filter(function (l) { return l.job === job; })[0]; }
  function key(l, e) { return l.job + ":" + e.seq; }
  function find(k) {
    var parts = String(k || "").split(":"), l = lane(parts[0]);
    if (!l) { return null; }
    var e = l.events.filter(function (x) { return String(x.seq) === parts[1]; })[0];
    return e ? {lane: l, e: e} : null;
  }
  function rules() { return (AC.policy || {}).rules || []; }
  function ruleOf(id, pol) {
    var list = (pol || AC.policy || {}).rules || [];
    for (var i = 0; i < list.length; i++) { if (list[i].id === id) { return {rule: list[i], n: i + 1, total: list.length}; } }
    return null;
  }
  function entry(seq) { return ((morning() || {}).audit || {}).entries ? morning().audit.entries[seq - 1] : null; }
  function clockAt(ms, ampm, seconds) {
    var s = Math.floor(((morning() || {}).start_clock_s || 0) + (ms || 0) / 1000), h = Math.floor(s / 3600) % 24;
    var out = ((h % 12) || 12) + ":" + pad(Math.floor(s / 60) % 60) + (seconds ? ":" + pad(s % 60) : "");
    return ampm ? out + (h < 12 ? " AM" : " PM") : out;
  }
  function span() { return Math.max(1, ((morning() || {}).span_ms || 1) * 1.03); }
  function isCall(e) { return e.kind === "call"; }
  function verdictOf(e) {
    if (e.kind === "cut") { return "quarantine"; }
    if (!e.verdict || (e.refused && e.verdict === "allow")) { return "refused"; }
    return e.verdict;
  }
  /* The mark an event gets on the trace, or null when an allowed call shows as a plain tile with its tool's icon. */
  function markOf(e) {
    if (e.kind === "cut") { return e.cuts && e.cuts.length ? {cls: "quarantine", icon: "quarantine"} : null; }
    if (e.kind === "call") {
      if (e.verdict === "ask") { return {cls: e.answer === "wait" ? "wait" : "ask", icon: "ask"}; }
      if (e.verdict === "deny") { return e.stop ? {cls: "stop", icon: "stop"} : {cls: "deny", icon: "deny"}; }
      if (!e.verdict || e.refused) { return {cls: "refused", icon: "deny"}; }
      return null;
    }
    if (e.kind === "budget") { return {cls: "budget", icon: "budget"}; }
    if (e.kind === "end" && e.state === "done") { return {cls: "done", icon: "done"}; }
    return null;
  }
  /* The family a tile counts toward in the counts strip. */
  var FAMILY = {allow: "allow", ask: "ask", wait: "ask", deny: "deny", stop: "deny", refused: "deny", quarantine: "quarantine",
    done: "done", budget: "budget"};
  function familyOf(e) {
    var mk = markOf(e);
    return mk ? FAMILY[mk.cls] : isCall(e) ? "allow" : null;
  }
  ACP.markOf = markOf;
  function label(e, l) {
    var what = e.kind === "call" ? tab("ui.tool", e.tool) + " " + (e.target || "") : e.kind === "cut" ? e.url || "" : e.kind;
    return clockAt(e.at_ms, true) + ", " + l.job + ", " + what + ", " + (e.kind === "end" ? tab("ui.state", e.state) :
      tab("ui.verdict", verdictOf(e)));
  }
  function defaultSel() {
    var order = [["quarantine"], ["stop", "deny"], ["wait", "ask"], ["done"]];
    for (var i = 0; i < order.length; i++) {
      var ls = lanes();
      for (var j = 0; j < ls.length; j++) {
        var hit = ls[j].events.filter(function (e) { var m = markOf(e); return m && order[i].indexOf(m.cls) >= 0; })[0];
        if (hit) { return key(ls[j], hit); }
      }
    }
    var l0 = lanes()[0];
    return l0 && l0.events.length ? key(l0, l0.events[l0.events.length - 1]) : null;
  }

  /* ------------------------------------------------------------------ the trace */
  /* The morning's counts, up to a moment in the replay or for the whole morning. */
  function counts(t) {
    var c = {calls: 0, allow: 0, ask: 0, deny: 0, quarantine: 0, done: 0, budget: 0, cost: 0};
    lanes().forEach(function (l) {
      l.events.forEach(function (e) {
        if (t !== undefined && t !== null && e.at_ms > t) { return; }
        if (e.kind === "model") { c.cost += e.cost_micro || 0; }
        if (isCall(e)) { c.calls++; }
        var fam = familyOf(e);
        if (fam) { c[fam]++; }
      });
    });
    return c;
  }
  function costUntil(l, t) {
    return l.events.reduce(function (n, e) { return n + (e.kind === "model" && e.at_ms <= t ? e.cost_micro || 0 : 0); }, 0);
  }
  /* The counts strip doubles as the legend: each swatch is the tile it counts, and a click finds the next one. */
  var KPIS = ["calls", "allow", "ask", "deny", "quarantine", "done", "cost"];
  var SWATCH = {allow: "shell", ask: "ask", deny: "deny", quarantine: "quarantine", done: "done"};
  function kpiValue(k, c) { return k === "cost" ? money(c.cost) : String(c[k]); }
  function kpis(c) {
    var names = u("ui.kpi") || {};
    return "<div class='kpis'>" + KPIS.map(function (k) {
      var sw = SWATCH[k] ? "<span class='sw sw-" + k + "'>" + icon(SWATCH[k]) + "</span>" : "";
      var inner = "<b data-kpi='" + k + "'>" + esc(kpiValue(k, c)) + "</b><span>" + sw + esc(names[k] || k) + "</span>";
      return SWATCH[k] ? "<button type='button' class='kpi k-" + k + "' data-pick='" + k + "'>" + inner + "</button>" :
        "<div class='kpi k-" + k + "'>" + inner + "</div>";
    }).join("") + "</div>";
  }
  /* A lane: the model's turns as small rings on the rail, and each call after its turn as a tile, in the order they ran.
     Allowed calls show their tool, and anything the policy, the reader or the budget stepped into shows its verdict. */
  function tile(l, e) {
    var mk = markOf(e);
    if (!mk && !isCall(e)) { return ""; }
    return "<button type='button' class='" + (mk ? "mk " + mk.cls : "tk") + "' data-ev='" + esc(key(l, e)) + "' data-at='" + e.at_ms +
      "' aria-label='" + esc(label(e, l)) + "'>" + icon(mk ? mk.icon : e.tool) + "</button>";
  }
  function laneSeq(l) {
    var out = "";
    l.events.forEach(function (e) {
      if (e.kind === "model") {
        out += "<span class='turn' data-turn='" + esc(key(l, e)) + "' data-at='" + Math.max(l.start_ms, e.at_ms - (e.ms || 0)) + "'></span>";
      } else {
        out += tile(l, e);
      }
    });
    return out + "<span class='tail' data-at='" + l.end_ms + "'></span>";
  }
  function renderTrace() {
    var m = morning(), host = $("#v-trace");
    if (!host) { return; }
    hideTip();
    if (!m) { host.innerHTML = "<p class='muted'>" + esc(word("ui.empty")) + "</p>"; return; }
    var legend = u("ui.legend") || {};
    var html = "<div class='trace" + (S.replaying ? " replaying" : "") + "' id='trace'><div class='progress' aria-hidden='true'><i></i></div>" +
      "<div class='th'><h1 id='t-title'>" +
      esc(word("ui.title_morning", {date: m.date, start: clockAt(0, true), end: clockAt(m.span_ms, true)})) + "</h1><span class='mchip'>" +
      esc(m.label) + "</span><span class='clock' id='t-clock' aria-hidden='true'></span><span class='rec'>" + esc(word("ui.recorded")) + "</span></div>" +
      "<p class='lead'>" + esc(word("ui.trace_lead")) + "</p>" + kpis(counts()) + "<div class='lanes'>";
    lanes().forEach(function (l) {
      var calls = l.events.filter(isCall).length;
      html += "<div class='lrow' data-row='" + esc(l.job) + "'><button type='button' class='lab' data-lane='" + esc(l.job) + "'><span class='lname'><b>" +
        esc(l.job) + "</b><span class='kind'>" + esc(l.kind) + "</span>" + icon("open", "go") + "</span><span class='pill p-" +
        esc(l.state) + "' data-at='" + l.end_ms + "'>" + esc(laneState(l)) + "</span></button><div class='lane' data-job='" + esc(l.job) +
        "'><div class='seq'>" + laneSeq(l) + "</div></div><div class='lmeta'><b data-cost='" + esc(l.job) + "'>" + esc(money(l.cost_micro)) +
        "</b><span>" + esc(word("ui.running", {minutes: duration(l.end_ms - l.start_ms), calls: calls})) + "</span></div></div>";
    });
    html += "</div><div class='tfoot'><span class='tturn'><span class='turn' aria-hidden='true'></span>" + esc(legend.turn || "") +
      "</span><span class='hint'>" + esc(word("ui.trace_hint")) + "</span></div></div><div class='detail card' id='detail'></div>";
    host.innerHTML = html;
    markSel();
    renderDetail();
  }
  function laneState(l) {
    var answer = S.answers[l.job];
    if (l.state === "waiting" && answer) { return tab("ui.lane_answer", answer); }
    return tab("ui.state", l.state);
  }
  /* On a desktop the page never scrolls and the long parts scroll inside their cards, so a view that draws itself again
     after a click keeps where each of those parts was, named by data-keep, unless the content under it changed. */
  function scrolls(root) {
    var out = {};
    $$("[data-keep]", root).forEach(function (el) { out[el.getAttribute("data-keep")] = el.scrollTop || 0; });
    return out;
  }
  function restore(root, spots, skip) {
    $$("[data-keep]", root).forEach(function (el) {
      var k = el.getAttribute("data-keep");
      if (spots[k] && !(skip && skip[k])) { el.scrollTop = spots[k]; }
    });
  }
  /* Positions from data attributes, through the CSSOM, so the page needs no inline styles. */
  function place(root) {
    $$("[data-pct]", root).forEach(function (el) { el.style.width = el.getAttribute("data-pct") + "%"; });
    $$("[data-at-pct]", root).forEach(function (el) { el.style.left = el.getAttribute("data-at-pct") + "%"; });
  }
  function markSel() {
    $$(".mk, .tk").forEach(function (el) { el.classList.toggle("sel", el.getAttribute("data-ev") === S.sel); });
  }
  function select(k, focus) {
    if (!find(k)) { return; }
    S.sel = k;
    markSel();
    renderDetail();
    writeHash();
    if (focus) { var el = $("[data-ev='" + k + "']"); if (el && el.focus) { el.focus(); } }
  }
  ACP.select = select;
  /* A count in the strip selects the next tile it counts, so pressing it again walks through them. */
  function pick(fam) {
    var list = [];
    lanes().forEach(function (l) { l.events.forEach(function (e) { if (familyOf(e) === fam) { list.push(key(l, e)); } }); });
    if (!list.length || S.replaying) { return; }
    select(list[(list.indexOf(S.sel) + 1) % list.length]);
  }
  ACP.pick = pick;

  /* ------------------------------------------------------------------ the selected event */
  function auditRef(e) {
    var seq = (e.audit || [])[0], en = seq ? entry(seq) : null;
    return en ? "<span class='hash'>" + esc(word("ui.audit_ref", {seq: seq, hash: short(en.hash), prev: seq - 1})) + "</span>" : "";
  }
  function highlight(text, needles, cls) {
    var out = esc(text);
    (needles || []).forEach(function (n) {
      if (n) { out = out.split(esc(n)).join("<span class='" + cls + "'>" + esc(n) + "</span>"); }
    });
    return out;
  }
  function host(url) { var m = /^[a-z]+:\/\/([^/]+)/i.exec(url || ""); return m ? m[1] : url; }
  function box(title, body, ico) { return "<div class='box'><h3>" + (ico ? icon(ico) : "") + esc(title) + "</h3>" + body + "</div>"; }
  function callLine(e) {
    return "<p class='callline'><span class='tag'>" + esc(tab("ui.tool", e.tool)) + "</span><code class='cmd'>" + esc(e.target) + "</code></p>";
  }
  function nextSay(l, e) {
    var after = l.events.filter(function (x) { return x.seq > e.seq && x.kind === "model" && x.text; })[0];
    return after ? "<p class='note'>" + esc(after.text) + "</p>" : "";
  }
  /* What the agent did next: its next call, or the session's end. */
  function nextStep(l, e) {
    var after = l.events.filter(function (x) { return x.seq > e.seq && (isCall(x) || x.kind === "end"); })[0];
    if (!after) { return ""; }
    if (after.kind === "end") { return "<p>" + esc(word("ui.session_ended", {state: tab("ui.state", after.state)})) + "</p>"; }
    return "<p class='note'>" + esc(word("ui.next_call")) + "</p>" + callLine(after);
  }
  function quarantineBoxes(l, e) {
    var steps = ["ui.q_step1", "ui.q_step2", "ui.q_step3", "ui.q_step4"].map(function (k, i) {
      return "<li><span class='n'>" + (i + 1) + "</span><span>" + esc(word(k)) + "</span></li>";
    }).join("");
    return box(word("ui.q_said"), "<div class='page' id='q-said'><span class='url'>" +
        esc(word("ui.q_url", {host: host(e.url), job: l.job})) + "</span>" + highlight(e.said, e.cuts, "inj") + "</div>", "fetch") +
      box(word("ui.q_given"), "<div class='page' id='q-given'><span class='url'>" + esc(host(e.url)) + "</span>" +
        highlight(e.given, [CUT_MARK], "cut") + "</div><p class='note'>" + esc(word("ui.q_note")) + "</p>", "quarantine") +
      box(word("ui.q_why"), "<ul class='why'>" + steps + "</ul>", "next");
  }
  /* Where the deciding rule sits in the policy: the rules above it didn't match, and nothing below it was read. */
  function rulePos(r) {
    var out = "";
    for (var i = 1; i <= r.total; i++) { out += "<i class='" + (i < r.n ? "past" : i === r.n ? "hit r-" + esc(r.rule.verdict) : "") + "'></i>"; }
    return "<span class='rulepos' aria-hidden='true'>" + out + "</span>";
  }
  function ruleBox(e) {
    var r = ruleOf(e.rule);
    var body = r ? "<b>" + esc(r.rule.label) + "</b><p>" + esc(r.rule.why) + "</p>" + rulePos(r) + "<p class='note'>" +
      esc(word("ui.rule_line", {n: r.n, total: r.total})) + "</p>" : "<p>" + esc(word("ui.no_rule")) + "</p>";
    return box(word("ui.rule_box"), "<div class='rulecard'>" + body + "</div>", "rule");
  }
  function answerBlock(l) {
    var a = S.answers[l.job];
    if (a) { return "<p>" + esc(word(a === "approve" ? "ui.you_approved" : "ui.you_denied")) + "</p>"; }
    return "<p>" + esc(word("ui.ask_wait")) + "</p><div class='answers'><button type='button' class='btn' data-answer='approve' " +
      "data-job='" + esc(l.job) + "'>" + esc(word("ui.approve")) + "</button><button type='button' class='btn ghost' " +
      "data-answer='deny' data-job='" + esc(l.job) + "'>" + esc(word("ui.deny")) + "</button></div>";
  }
  function callBoxes(l, e) {
    var first = callLine(e);
    if (e.ran) {
      first += "<p class='note'>" + esc(word("ui.allowed")) + "</p><pre class='out'>" + esc(e.output || word("ui.no_output")) + "</pre>";
      if (e.masked) { first += "<p class='note'>" + esc(word("ui.masked_note")) + "</p>"; }
    } else if (e.refused && e.verdict === "allow") {
      first += "<p class='note'>" + esc(word("ui.refused_after")) + "</p>";
    }
    var next;
    if (e.verdict === "ask" && e.answer === "wait") { next = answerBlock(l); }
    else if (e.verdict === "ask") { next = "<p>" + esc(word("ui.ask_scripted", {answer: tab("ui.answer", e.answer)})) + "</p>" + nextSay(l, e); }
    else if (e.verdict === "deny") { next = "<p>" + esc(word(e.stop ? "ui.deny_stop" : "ui.deny_go")) + "</p>" + (e.stop ? "" : nextSay(l, e)); }
    else { next = nextSay(l, e) + nextStep(l, e); }
    return box(word("ui.call_box"), first, e.tool) + ruleBox(e) + box(word("ui.next_box"), next, "next");
  }
  function doneBoxes(l, e) {
    var checks = (l.checks || []).map(function (c) {
      return "<li><span class='n " + (c.ok ? "ok" : "bad") + "'>" + icon(c.ok ? "done" : "deny") + "</span><span>" + esc(c.what) +
        (c.detail && typeof c.detail === "string" ? " (" + esc(c.detail) + ")" : "") + "</span></li>";
    }).join("");
    return box(word("ui.done_task"), "<div class='page'>" + esc(l.task) + "</div>", "read") +
      box(word("ui.done_reply"), "<div class='page'>" + esc(e.reply || l.reply) + "</div>", "reply") +
      box(word("ui.done_checks"), "<ul class='why'>" + checks + "</ul>", "done");
  }
  /* The budget note's words: the stop, the warning that rode with the last reply the money paid for, or the one at 80%. */
  function budgetWord(e) {
    return e.level === "stop" ? "ui.budget_stop" : e.reason === "last" ? "ui.budget_last" : "ui.budget_warn";
  }
  function budgetBoxes(l, e) {
    var share = Math.min(100, ((e.spent_micro || 0) / Math.max(1, e.limit_micro || 1)) * 100);
    return box(word("ui.budget_label"), "<div class='meter'><i data-pct='" + share.toFixed(1) + "'></i><b data-at-pct='80'></b></div><p>" +
        esc(word("ui.spent_of", {spent: money(e.spent_micro), limit: money(e.limit_micro)})) + "</p>", "budget") +
      box(word("ui.next_box"), "<p>" + esc(word(budgetWord(e))) + "</p>", "next");
  }
  /* The selected event's chip: its verdict's icon and words, the same family of colors as its tile. */
  function chip(l, e) {
    var mk = markOf(e), cls = "allow", name = "shell", text = e.kind;
    if (e.kind === "end") { cls = e.state === "done" ? "done" : "deny"; name = e.state === "done" ? "done" : "stop"; text = tab("ui.state", e.state); }
    else if (e.kind === "cut") { cls = "quarantine"; name = "quarantine"; text = tab("ui.verdict", "quarantine"); }
    else if (e.kind === "budget") { cls = "budget"; name = "budget"; text = word("ui.budget_label"); }
    else if (isCall(e)) {
      cls = mk ? mk.cls : "allow";
      name = mk ? mk.icon : e.tool;
      text = tab("ui.verdict", verdictOf(e));
      if (e.answer === "wait") { text += " · " + (S.answers[l.job] ? tab("ui.lane_answer", S.answers[l.job]) : tab("ui.answer_short", "wait")); }
    }
    return "<span class='vchip c-" + cls + "'>" + icon(name) + esc(text) + "</span>";
  }
  /* Every event the trace shows, lane by lane, for the inspector's previous and next. */
  function shownKeys() {
    var out = [];
    lanes().forEach(function (l) { l.events.forEach(function (e) { if (markOf(e) || isCall(e)) { out.push(key(l, e)); } }); });
    return out;
  }
  function stepSel(dir) {
    var list = shownKeys(), i = list.indexOf(S.sel), next = list[i + dir];
    if (i >= 0 && next) { select(next); }
  }
  ACP.step = stepSel;
  function inspectorHead(l, e) {
    var list = shownKeys(), i = list.indexOf(key(l, e));
    var what = isCall(e) ? tab("ui.tool", e.tool) + " " + (e.target || "") : e.kind === "cut" ? e.url || "" : "";
    return "<div class='ihead'>" + chip(l, e) + "<span class='ititle'><b>" + esc(l.job) + "</b>" + (what ? "<code>" + esc(what) + "</code>" : "") +
      "</span><span class='itime'>" + esc(clockAt(e.at_ms, true, true)) + "</span><span class='grow'></span>" + auditRef(e) +
      "<span class='steps'><button type='button' class='stepb' data-step='-1' aria-label='" + esc(word("ui.step_prev")) + "'" +
      (i <= 0 ? " disabled" : "") + ">" + icon("back") + "</button><button type='button' class='stepb' data-step='1' aria-label='" +
      esc(word("ui.step_next")) + "'" + (i < 0 || i >= list.length - 1 ? " disabled" : "") + ">" + icon("open") + "</button></span></div>";
  }
  function renderDetail() {
    var hostEl = $("#detail"), f = find(S.sel);
    if (!hostEl) { return; }
    if (!f) { hostEl.innerHTML = ""; return; }
    var l = f.lane, e = f.e, cols, two = false;
    if (e.kind === "cut") { cols = quarantineBoxes(l, e); }
    else if (e.kind === "call") { cols = callBoxes(l, e); }
    else if (e.kind === "end") { cols = doneBoxes(l, e); }
    else if (e.kind === "budget") { cols = budgetBoxes(l, e); two = true; }
    else { cols = box(e.kind, ""); }
    hostEl.innerHTML = inspectorHead(l, e) + "<div class='icols" + (two ? " two" : "") + "'>" + cols + "</div>";
    place(hostEl);
    drawThread(true);
  }
  /* The quarantine's thread: a curve from the sentence the reader cut, in what the page said, to the marker it left in
     what the agent was given, red where the note was and cyan where the reader's marker is. Drawn from the boxes' real
     positions, so it's redrawn when the window changes. */
  function drawThread(animate) {
    var hostEl = $("#detail"), a = $("#q-said .inj"), b = $("#q-given .cut");
    var old = $("#detail .threads");
    if (old) { old.remove(); }
    if (!hostEl || !a || !b || !hostEl.getBoundingClientRect || phone()) { return; }
    var d = hostEl.getBoundingClientRect(), ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    var ya = ra.top + ra.height / 2, yb = rb.top + rb.height / 2;
    /* The columns scroll on their own, so the thread waits while either end is scrolled out of its column. */
    if (!inView(a, ya) || !inView(b, yb)) { return; }
    var ox = d.left + (hostEl.clientLeft || 0), oy = d.top + (hostEl.clientTop || 0);
    var x1 = ra.right - ox, y1 = ya - oy, x2 = rb.left - ox, y2 = yb - oy;
    var g = Math.max(30, (x2 - x1) * 0.5), f = function (n) { return Math.round(n * 10) / 10; };
    var wrap = doc.createElement("div");
    wrap.className = "threads";
    wrap.setAttribute("aria-hidden", "true");
    wrap.innerHTML = "<svg width='" + f(hostEl.clientWidth || d.width) + "' height='" + f(hostEl.clientHeight || d.height) + "'><defs>" +
      "<linearGradient id='thread-ink' gradientUnits='userSpaceOnUse' x1='" + f(x1) + "' y1='0' x2='" + f(x2) + "' y2='0'><stop offset='0' " +
      "stop-color='#ef4444'/><stop offset='1' stop-color='#06b6d4'/></linearGradient></defs><path pathLength='1' stroke='url(#thread-ink)'" +
      (animate ? "" : " class='still'") + " d='M" + f(x1) + " " + f(y1) + " C" + f(x1 + g) + " " + f(y1) + " " + f(x2 - g) + " " + f(y2) + " " + f(x2) +
      " " + f(y2) + "'/><circle class='a' cx='" + f(x1) + "' cy='" + f(y1) + "' r='3.5'/><circle class='b' cx='" + f(x2) + "' cy='" + f(y2) +
      "' r='3.5'/></svg>";
    hostEl.appendChild(wrap);
  }
  function inView(el, y) {
    var col = el.closest ? el.closest(".box") : null, r = col && col.getBoundingClientRect ? col.getBoundingClientRect() : null;
    return !r || (y >= r.top + 4 && y <= r.bottom - 4);
  }

  /* ------------------------------------------------------------------ the tooltip over a tile or a turn */
  function tipHtml(el) {
    var f = find(el.getAttribute("data-ev") || el.getAttribute("data-turn"));
    if (!f) { return ""; }
    var l = f.lane, e = f.e, head = "<p class='pt'>" + esc(clockAt(e.at_ms, true, true)) + " · " + esc(l.job) + "</p>";
    if (e.kind === "model") {
      var secs = ((e.ms || 0) / 1000).toFixed(1) + " s";
      var line = e.calls ? word("ui.turn_calls", {secs: secs, calls: e.calls === 1 ? word("ui.one_call") : word("ui.n_calls", {n: e.calls})}) :
        word("ui.turn_last", {secs: secs});
      return head + "<p>" + esc(line) + "</p>" + (e.text ? "<p class='said'>" + esc(trim(e.text, 160)) + "</p>" : "");
    }
    var mk = markOf(e), r = isCall(e) ? ruleOf(e.rule) : null;
    var what = isCall(e) ? tab("ui.tool", e.tool) + " " + (e.target || "") : e.kind === "cut" ? e.url || "" : "";
    var verdict = e.kind === "end" ? tab("ui.state", e.state) : e.kind === "budget" ? word("ui.budget_label") :
      tab("ui.verdict", verdictOf(e)) + (r ? " · " + r.rule.label : "");
    return head + (what ? "<code>" + esc(trim(what, 96)) + "</code>" : "") + "<p class='pv c-" + (mk ? mk.cls : "allow") + "'>" +
      icon(mk ? mk.icon : e.tool) + esc(verdict) + "</p>";
  }
  function showTip(el) {
    var pop = $("#pop");
    if (!pop || !el || phone() || S.tour || !el.getBoundingClientRect) { return; }
    var html = tipHtml(el);
    if (!html) { return; }
    pop.innerHTML = html;
    pop.hidden = false;
    var r = el.getBoundingClientRect(), W = win.innerWidth || 1600, w = pop.offsetWidth || 260;
    var cx = Math.max(w / 2 + 8, Math.min(W - w / 2 - 8, r.left + r.width / 2));
    pop.style.left = Math.round(cx + (win.scrollX || 0)) + "px";
    pop.style.top = Math.round(r.top + (win.scrollY || 0)) + "px";
  }
  function hideTip() { var pop = $("#pop"); if (pop) { pop.hidden = true; } }
  // Dark mode (11/20). Light is the default, and the switch carries its state for screen readers.
  function setDark(on) {
    doc.body.classList.toggle("dark", !!on);
    var b = $("#theme");
    if (b) { b.setAttribute("aria-pressed", on ? "true" : "false"); }
    if (typeof drawThread === "function") { drawThread(false); }
  }
  window.ACP = window.ACP || {};
  window.ACP.dark = setDark;

  function tipTarget(t) { return t && t.closest ? t.closest("#v-trace [data-ev], #v-trace [data-turn]") : null; }

  /* ------------------------------------------------------------------ the visitor's answer to the waiting push */
  function answer(job, a) {
    var l = lane(job);
    if (!l || S.answers[job]) { return; }
    var e = l.events.filter(function (x) { return isCall(x) && x.answer === "wait"; })[0];
    S.answers[job] = a;
    chain();
    S.chain = Aud.append(S.chain, {at: new Date().toISOString().slice(0, 19), session: job, actor: "you", action: "answer",
      target: e ? e.target : "", verdict: a === "approve" ? "approve" : "decline", rule: e ? e.rule : "", result: ""});
    render();
  }
  ACP.answer = answer;

  /* ------------------------------------------------------------------ the replay of the morning */
  /* The morning plays in about ten seconds: the sessions at one speed, and the quiet stretches between them five times
     faster. Tiles arrive when their calls did, and the counts, each lane's cost, the clock and the bar run with them. */
  var R = {run: 0, last: 0};
  var REPLAY_MS = 16000, QUIET = 5;
  function busyAt(t) { return lanes().some(function (l) { return t >= l.start_ms - 600 && t <= l.end_ms + 300; }); }
  function tick(run) {
    if (run !== R.run || !S.replaying) { return; }
    var now = Date.now(), dt = Math.max(16, Math.min(100, now - R.last));
    R.last = now;
    S.t += dt * (span() / REPLAY_MS) * (busyAt(S.t) ? 1 : QUIET);
    showUntil(S.t);
    if (S.t >= span()) { endReplay(); return; }
    (win.requestAnimationFrame || function (fn) { return win.setTimeout(fn, 16); })(function () { tick(run); });
  }
  function showUntil(t) {
    $$("#v-trace [data-at]").forEach(function (el) { el.classList.toggle("later", Number(el.getAttribute("data-at")) > t); });
    lanes().forEach(function (l) {
      var row = $("#v-trace .lrow[data-row='" + l.job + "']"), cost = $("#v-trace [data-cost='" + l.job + "']");
      if (row) { row.classList.toggle("idle", t < l.start_ms); row.classList.toggle("live", t >= l.start_ms && t <= l.end_ms); }
      if (cost) { cost.textContent = money(costUntil(l, t)); }
    });
    var c = counts(t);
    $$("#v-trace [data-kpi]").forEach(function (el) { el.textContent = kpiValue(el.getAttribute("data-kpi"), c); });
    var bar = $("#v-trace .progress i"), clock = $("#t-clock");
    if (bar) { bar.style.width = Math.min(100, (t / span()) * 100).toFixed(2) + "%"; }
    if (clock) { clock.textContent = clockAt(t, true, true); }
  }
  function startReplay() {
    if (S.view === "session") { startTerminal(); return; }
    setView("trace");
    if (calm()) { endReplay(); return; }
    R.run += 1;
    S.replaying = true;
    S.t = 0;
    var card = $("#trace");
    if (card) { card.classList.add("replaying"); }
    showUntil(0);
    R.last = Date.now();
    tick(R.run);
  }
  function endReplay() {
    R.run += 1;
    S.replaying = false;
    S.t = null;
    renderTrace();
    select(defaultSel());
  }
  ACP.endReplay = endReplay;
  /* ------------------------------------------------------------------ a session */
  function termLines(l) {
    var lines = ["<p class='prompt'>❯ " + esc(l.task) + "</p>"];
    l.events.forEach(function (e) {
      var v = verdictOf(e), k = key(l, e), mk = markOf(e);
      if (e.kind === "model" && e.text) { lines.push("<p class='say'>" + esc(e.text) + "</p>"); }
      else if (isCall(e)) {
        var r = ruleOf(e.rule), why = (e.answer ? tab("ui.answer_short", e.answer) : tab("ui.verdict", v)) + (r ? " · " + r.rule.label : "");
        var line = "<div class='cl v-" + (mk ? mk.cls : "allow") + "' data-ev='" + esc(k) + "'><span class='ico'>" + icon(mk ? mk.icon : e.tool) +
          "</span><b>" + esc(tab("ui.tool", e.tool)) + "</b><code class='cmd'>" + esc(e.target) + "</code><span class='v'>" + esc(why) + "</span>";
        if (e.output && (e.ran || e.refused)) {
          line += "<button type='button' class='toggle' data-out='" + esc(k) + "'>" + esc(word(S.open[k] ? "ui.hide_output" : "ui.show_output")) +
            "</button>" + (S.open[k] ? "<pre class='tout'>" + esc(e.output) + "</pre>" : "");
        }
        lines.push(line + "</div>");
        if (e.answer === "wait") {
          lines.push("<div class='pause'><b>" + esc(word("ui.paused")) + "</b> " + answerBlock(l) + "</div>");
        }
      } else if (e.kind === "cut" && e.cuts && e.cuts.length) {
        lines.push("<div class='cl v-quarantine'><span class='ico'>" + icon("quarantine") + "</span><b>" + esc(tab("ui.verdict", "quarantine")) +
          "</b><code class='cmd'>" + esc(e.url) + "</code><span class='v'>" + esc(e.cuts.length) + "</span></div>");
      } else if (e.kind === "masked") {
        lines.push("<div class='cl v-quarantine'><span class='ico'>" + icon("quarantine") + "</span><b>" + esc(tab("ui.verdict", "masked")) +
          "</b><code class='cmd'>" + esc(e.target) + "</code></div>");
      } else if (e.kind === "budget") {
        lines.push("<p class='say'>" + esc(word(budgetWord(e))) + "</p>");
      } else if (e.kind === "end" && e.state !== "waiting") {
        lines.push("<p class='endline'>" + esc(word("ui.session_ended", {state: tab("ui.state", e.state)})) + "</p>");
      }
    });
    return lines;
  }
  /* A session in miniature for the list: one square per call in the order they ran, colored like its tile. */
  function strip(l) {
    var cells = "";
    l.events.forEach(function (e) {
      var mk = markOf(e);
      if (mk) { cells += "<i class='s-" + mk.cls + "'></i>"; } else if (isCall(e)) { cells += "<i></i>"; }
    });
    return "<span class='strip' aria-hidden='true'>" + cells + "</span>";
  }
  function renderSession() {
    var hostEl = $("#v-session"), m = morning();
    if (!hostEl || !m) { return; }
    S.job = S.job && lane(S.job) ? S.job : (lanes()[1] || lanes()[0] || {}).job;
    var l = lane(S.job);
    var list = lanes().map(function (x) {
      return "<button type='button' class='" + (x.job === l.job ? "on" : "") + "' data-session='" + esc(x.job) + "'><b>" +
        esc(x.job) + "</b><span class='who'>" + esc(m.label) + "</span>" + pill(x.state, laneState(x)) + strip(x) + "</button>";
    }).join("");
    var lines = termLines(l), shown = S.term && S.term.job === l.job ? S.term.n : lines.length;
    var body = lines.slice(0, shown).join("");
    var calls = l.events.filter(isCall), share = Math.min(100, (l.cost_micro / Math.max(1, l.budget_micro)) * 100);
    var events = calls.slice().reverse().map(function (e) {
      var r = ruleOf(e.rule), mk = markOf(e);
      return "<li class='e-" + (mk ? mk.cls : "allow") + "'><span class='t'>" + esc(clockAt(e.at_ms)) + "</span><span><code>" + esc(e.target) +
        "</code><small>" + esc(tab("ui.verdict", verdictOf(e))) + (r ? " · " + esc(r.rule.label) : "") + "</small></span></li>";
    }).join("");
    var elsewhere = [];
    lanes().forEach(function (o) {
      if (o.job === l.job) { return; }
      o.events.forEach(function (e) {
        var mk = markOf(e);
        if (mk && mk.cls !== "done") {
          elsewhere.push("<li class='e-" + mk.cls + "'><span class='t'>" + esc(clockAt(e.at_ms)) + "</span><span><code>" + esc(e.target || e.url || "") +
            "</code><small>" + esc(o.job) + " · " + esc(tab("ui.verdict", verdictOf(e))) + "</small></span></li>");
        }
      });
    });
    var spots = scrolls(hostEl), sameJob = S.shownJob === l.job;
    hostEl.innerHTML = "<div class='sessions'><nav class='slist' aria-label='sessions'>" + list + "</nav><div class='term'><div class='thead'>" +
      esc(word("ui.term_head", {job: l.job, model: m.label})) + "</div><div class='tbody' id='tbody' data-keep='term'>" + body + "</div></div>" +
      "<div class='side' data-keep='side'><div class='card'><h3>" + esc(word("ui.budget_label")) + "</h3><div class='kv'><span>" +
      esc(word("ui.spent_of", {spent: money(l.cost_micro), limit: money(l.budget_micro)})) + "</span></div><div class='meter'><i data-pct='" +
      share.toFixed(1) + "'></i><b data-at-pct='80'></b></div><div class='kv'><span>" + esc(word("ui.running", {minutes: duration(l.end_ms - l.start_ms),
        calls: calls.length})) + "</span></div></div><div class='card'><h3>" + esc(word("ui.events")) + "</h3><ul class='evlist' data-keep='events'>" + events +
      "</ul></div><div class='card'><h3>" + esc(word("ui.elsewhere")) + "</h3><ul class='evlist'>" + elsewhere.join("") + "</ul></div></div></div>";
    /* Another session starts at its top, a terminal that's replaying follows its newest line, and anything else stays put. */
    restore(hostEl, spots, sameJob ? null : {term: true, events: true});
    var tb = $("#tbody");
    if (tb && S.term && S.term.job === l.job && tb.scrollHeight) { tb.scrollTop = tb.scrollHeight; }
    S.shownJob = l.job;
    place(hostEl);
  }
  function duration(ms) {
    var s = Math.round((ms || 0) / 1000);
    return s >= 60 ? Math.floor(s / 60) + " min " + pad(s % 60) + " s" : s + " s";
  }
  var TT = {timer: 0};
  function startTerminal() {
    var l = lane(S.job);
    if (!l) { return; }
    var total = termLines(l).length;
    if (calm()) { S.term = null; renderSession(); return; }
    S.term = {job: l.job, n: 1};
    renderSession();
    win.clearTimeout(TT.timer);
    (function step() {
      if (!S.term || S.term.n >= total) { S.term = null; renderSession(); return; }
      S.term.n += 1;
      renderSession();
      var cmds = $$("#tbody .cmd"), last = cmds[cmds.length - 1];
      if (last) { typeOut(last); }
      TT.timer = win.setTimeout(step, 420);
    })();
  }
  function typeOut(el) {
    var full = el.textContent, i = 0;
    if (!full || calm()) { return; }
    el.classList.add("typing");
    (function next() {
      i = Math.min(full.length, i + 3);
      el.textContent = full.slice(0, i);
      if (i < full.length) { win.setTimeout(next, 12); } else { el.classList.remove("typing"); }
    })();
  }
  ACP.terminal = function () { return termLines(lane(S.job)).length; };

  /* ------------------------------------------------------------------ the policy and the simulator */
  function groupOf(r) {
    var t = r.tools || [];
    if (t.indexOf("fetch") >= 0) { return "web"; }
    if (t.length === 1 && t[0] === "shell") { return "shell"; }
    return "files";
  }
  /* Every recorded call decided again under the visitor's policy. A call whose outcome changes (it ran and now
     wouldn't, or the other way round) marks the calls after it in that session, since the agent would have seen
     something else, and a new stop marks them never reached. */
  function simulate(pol) {
    pol = pol || S.policy || AC.policy;
    var rows = {}, changes = [];
    lanes().forEach(function (l) {
      var shifted = false, stopped = false;
      rows[l.job] = l.events.filter(isCall).map(function (e) {
        var row = {e: e, now: null, state: stopped ? "never" : shifted ? "after" : "same"};
        if (stopped || !e.facts) { return row; }
        var d = Pol.decide(e.facts, pol);
        row.now = d;
        if (d.verdict !== e.verdict || d.rule !== e.rule || d.stop !== !!e.stop) {
          var ran = !!e.ran, runs = d.verdict === "allow" ? !e.refused && !layerHolds(e) : d.verdict === "ask" && e.verdict === "ask" ? ran : false;
          if (row.state === "same") { row.state = "changed"; }
          changes.push({job: l.job, e: e, d: d});
          if (runs !== ran) { shifted = true; }
          if (d.verdict === "deny" && d.stop) { stopped = true; }
        }
        return row;
      });
    });
    return {rows: rows, changes: changes};
  }
  function layerHolds(e) {
    var f = e.facts || {};
    if (f.outside) { return true; }
    if (f.tool === "fetch") { return !AC.names || !Object.keys(AC.names).some(function (k) { return AC.names[k].domain === f.host; }); }
    return false;
  }
  ACP.simulate = function (changesById) {
    var pol = clone(AC.policy);
    pol.rules.forEach(function (r) { if (changesById && changesById[r.id]) { r.verdict = changesById[r.id]; } });
    var out = simulate(pol);
    return {changes: out.changes.length, rows: out.rows, phrases: out.changes.map(phrase)};
  };
  function phrase(c) {
    var fill = {target: c.e.target && c.e.target.length > 60 ? c.e.target.slice(0, 59) + "…" : c.e.target, job: c.job}, k;
    if (c.d.verdict === "deny") { k = c.d.stop ? "ui.sim_deny_stop" : "ui.sim_deny"; }
    else if (c.d.verdict === "allow") { k = c.e.verdict === "ask" ? "ui.sim_allow" : "ui.sim_run"; }
    else { k = c.e.verdict === "deny" ? "ui.sim_to_ask" : "ui.sim_ask"; }
    var out = word(k, fill);
    return c.d.verdict === "allow" && layerHolds(c.e) ? out + " " + word("ui.sim_layer") : out;
  }
  function renderPolicies() {
    var hostEl = $("#v-policies"), m = morning();
    if (!hostEl || !m) { return; }
    S.policy = S.policy || clone(AC.policy);
    S.polJob = S.polJob && lane(S.polJob) ? S.polJob : (lanes()[1] || lanes()[0]).job;
    var list = [];
    S.policy.rules.forEach(function (r, i) {
      var orig = rules()[i] || {}, pats = (r.commands || r.paths || r.hosts || []).slice(0, 4);
      var more = (r.commands || r.paths || r.hosts || []).length - pats.length;
      var tri = ["allow", "ask", "deny"].map(function (v) {
        return "<button type='button' class='" + {allow: "a", ask: "k", deny: "d"}[v] + "' data-rule='" + esc(r.id) +
          "' data-verdict='" + v + "' aria-pressed='" + (r.verdict === v ? "true" : "false") + "'>" + esc(tab("ui.tri", v)) + "</button>";
      }).join("");
      list.push("<div class='rule" + (orig.verdict !== r.verdict ? " changed" : "") + "'><span class='num'>" + (i + 1) +
        "</span><span class='what' title='" + esc(r.why) + "'>" + esc(r.label) + "<span class='tag'>" + esc(tab("ui.group", groupOf(r))) +
        "</span></span><span class='tri' role='group' aria-label='" +
        esc(r.label) + "'>" + tri + "</span><span class='pat'>" + pats.map(function (p) { return "<code>" + esc(p) + "</code>"; }).join("") +
        (more > 0 ? "<code>+" + more + "</code>" : "") + "</span></div>");
    });
    var sim = simulate(), rowsHtml = (sim.rows[S.polJob] || []).map(function (row) {
      var e = row.e, rec = pill(verdictOf(e), tab("ui.verdict", verdictOf(e)) + (e.answer ? " · " + tab("ui.answer_short", e.answer) : ""));
      var yours = row.state === "never" ? esc(word("ui.never_reached")) : row.state === "same" ? "<span class='muted'>" + esc(word("ui.same")) + "</span>" :
        row.now && (row.now.verdict !== e.verdict || row.now.rule !== e.rule) ? pill(row.now.verdict, tab("ui.verdict", row.now.verdict)) +
          (row.state === "after" ? " <small class='muted'>" + esc(word("ui.after_change")) + "</small>" : "") :
          "<small class='muted'>" + esc(word("ui.after_change")) + "</small>";
      return "<tr class='" + (row.state === "changed" ? "chg" : row.state === "after" || row.state === "never" ? "dim" : "") + "'><td>" +
        esc(clockAt(e.at_ms)) + "</td><td>" + esc(tab("ui.tool", e.tool)) + "</td><td class='arg'>" + esc(e.target) + "</td><td>" + rec +
        "</td><td>" + yours + "</td></tr>";
    }).join("");
    var n = sim.changes.length, summary = n === 0 ? word("ui.sim_same") : n === 1 ? word("ui.sim_one") : word("ui.sim_changed", {n: n});
    var phrases = sim.changes.map(phrase).filter(function (p, i, all) { return all.indexOf(p) === i; }).slice(0, 3)
      .map(function (p) { return "<p>" + esc(p) + "</p>"; }).join("");
    var col = u("ui.col") || {}, l = lane(S.polJob), share = Math.min(100, (l.cost_micro / Math.max(1, l.budget_micro)) * 100);
    var head = (m.audit.entries || []).slice(-5).reverse().map(function (en) {
      return "<div><span class='h'>#" + en.seq + "</span>" + esc(en.action) + " " + esc(en.verdict) + " · " + esc(short(en.hash)) + "</div>";
    }).join("");
    var spots = scrolls(hostEl), sameJob = S.shownPolJob === S.polJob;
    hostEl.innerHTML = "<div class='pol'><section class='card' id='rules'><h2>" + esc(tab("ui.view_heads", "policies")) + "</h2><p class='lead'>" +
      esc(word("ui.policy_lead")) + "</p><div class='rlist' data-keep='rules'>" + list.join("") + "</div><p><button type='button' class='btn ghost' " +
      "id='reset-policy'>" + esc(word("ui.reset")) + "</button></p></section>" +
      "<section class='card'><div class='verdict' id='sim'><p><b>" + esc(summary) + "</b></p>" + phrases + "</div><div class='chips'>" +
      lanes().map(function (x) {
        return "<button type='button' class='" + (x.job === S.polJob ? "on" : "") + "' data-poljob='" + esc(x.job) + "'>" + esc(x.job) + "</button>";
      }).join("") + "</div><div class='scroll' data-keep='calls'><table class='calls'><thead><tr><th>" + esc(col.time) + "</th><th>" + esc(col.tool) +
      "</th><th>" + esc(col.call) + "</th><th>" + esc(col.recorded) + "</th><th>" + esc(col.yours) + "</th></tr></thead><tbody>" + rowsHtml +
      "</tbody></table></div></section><section class='card' data-keep='guard'><h3>" + esc(word("ui.guardrails")) + "</h3><div class='kv'><span>" +
      esc(word("ui.budget_label")) + "</span><span class='mono'>" + esc(word("ui.spent_of", {spent: money(l.cost_micro), limit: money(l.budget_micro)})) +
      "</span></div><div class='meter'><i data-pct='" + share.toFixed(1) + "'></i><b data-at-pct='80'></b></div><h3>" + esc(word("ui.stopped_head")) +
      "</h3><ul class='risk'>" + stoppedList() + "</ul><h3>" + esc(tab("ui.view_heads", "chain")) + "</h3><div class='chain'>" + head + "</div></section></div>";
    restore(hostEl, spots, sameJob ? null : {calls: true});
    S.shownPolJob = S.polJob;
    place(hostEl);
  }
  function stoppedList() {
    var c = {outside: 0, secrets: 0, hosts: 0, pages: 0, pushes: 0}, names = u("ui.stopped") || {};
    lanes().forEach(function (l) {
      l.events.forEach(function (e) {
        if (isCall(e)) {
          if (e.rule === "outside") { c.outside++; }
          if (e.rule === "secrets") { c.secrets++; }
          if ((e.facts || {}).tool === "fetch" && e.rule !== "listed") { c.hosts++; }
          if (e.answer === "wait") { c.pushes++; }
        }
        if (e.kind === "cut" && e.cuts && e.cuts.length) { c.pages++; }
      });
    });
    return Object.keys(c).map(function (k) { return "<li><span>" + esc(names[k] || k) + "</span><span class='mono'>" + c[k] + "</span></li>"; }).join("");
  }
  function setRule(id, verdict) {
    S.policy = S.policy || clone(AC.policy);
    S.policy.rules.forEach(function (r) { if (r.id === id) { r.verdict = verdict; } });
    renderPolicies();
  }
  ACP.setRule = setRule;

  /* ------------------------------------------------------------------ the audit log and the tamper test */
  function chain() {
    if (!S.chain) { S.chain = clone((morning() || {}).audit.entries || []); S.recorded = S.chain.length; }
    return S.chain;
  }
  function verifyAll() {
    var list = chain(), head = (morning() || {}).audit.head, v = Aud.verify(list, null);
    if (!v.ok) { return v; }
    if (list[S.recorded - 1] && list[S.recorded - 1].hash !== head) {
      return {ok: false, count: list.length, failed_at: S.recorded, why: "head"};
    }
    return v;
  }
  ACP.verify = verifyAll;
  function tamperTarget() {
    var list = chain(), pick = list.filter(function (en) { return en.rule === "secrets" && en.verdict === "deny"; })[0] ||
      list.filter(function (en) { return en.actor === "agent" && en.verdict === "ask"; })[0] || list[2] || list[0];
    return pick ? pick.seq : null;
  }
  function tamper(step) {
    var list = chain();
    if (step === "reset") {
      var mine = list.slice(S.recorded);
      S.chain = null;
      chain();
      mine.forEach(function (en) { S.chain = Aud.append(S.chain, en); });
      S.tamper = 0;
      S.tamperSeq = null;
      S.result = verifyAll();
    } else if (step === "verify") {
      S.result = verifyAll();
    } else if (step === "1" && !S.tamper) {
      S.tamperSeq = tamperTarget();
      var en = list[S.tamperSeq - 1];
      en.verdict = en.verdict === "allow" ? "deny" : "allow";
      S.tamper = 1;
      S.result = verifyAll();
    } else if (step === "2" && S.tamper === 1) {
      list[S.tamperSeq - 1].hash = Aud.entryHash(list[S.tamperSeq - 1]);
      S.tamper = 2;
      S.result = verifyAll();
    } else if (step === "3" && S.tamper === 2) {
      for (var i = S.tamperSeq; i < list.length; i++) {
        list[i].prev = list[i - 1].hash;
        list[i].hash = Aud.entryHash(list[i]);
      }
      S.tamper = 3;
      S.result = verifyAll();
    }
    renderAudit();
  }
  ACP.tamper = function (step) { tamper(step); return S.result; };
  function renderAudit() {
    var hostEl = $("#v-audit"), m = morning();
    if (!hostEl || !m) { return; }
    var list = chain(), cols = u("ui.audit_cols") || {}, r = S.result, bad = r && !r.ok ? r.failed_at : null;
    var result = !r ? "" : r.ok ? "<p class='result ok'>" + esc(word("ui.verified", {n: r.count})) + "</p>" :
      "<p class='result bad'>" + esc(word("ui.failed", {seq: r.failed_at, why: tab("ui.why", r.why)})) + "</p>";
    var buttons = "<button type='button' class='btn' data-audit='verify'>" + esc(word("ui.verify")) + "</button>" +
      "<button type='button' class='btn ghost' data-audit='1'" + (S.tamper ? " disabled" : "") + ">" + esc(word("ui.tamper1")) + "</button>" +
      "<button type='button' class='btn ghost' data-audit='2'" + (S.tamper !== 1 ? " disabled" : "") + ">" + esc(word("ui.tamper2")) + "</button>" +
      "<button type='button' class='btn ghost' data-audit='3'" + (S.tamper !== 2 ? " disabled" : "") + ">" + esc(word("ui.tamper3")) + "</button>" +
      "<button type='button' class='link' data-audit='reset'" + (S.tamper ? "" : " disabled") + ">" + esc(word("ui.tamper_reset")) + "</button>";
    var rows = list.map(function (en) {
      var cls = en.seq === bad ? "bad" : en.actor === "you" ? "mine" : en.seq === S.tamperSeq ? "changed" : "";
      return "<tr class='" + cls + "'><td class='m'>" + en.seq + "</td><td class='m'>" + esc(String(en.at).slice(11, 19)) + "</td><td>" +
        esc(en.session) + "</td><td>" + esc(tab("ui.actor", en.actor)) + "</td><td>" + esc(en.action) + "</td><td class='m'>" + esc(en.target) +
        "</td><td>" + (en.verdict ? pill(en.verdict, en.verdict) : "") + "</td><td>" + esc(en.rule) + "</td><td class='m'>" + esc(short(en.hash)) +
        "</td></tr>";
    }).join("");
    var spots = scrolls(hostEl);
    hostEl.innerHTML = "<div class='audit card'><h2>" + esc(tab("ui.view_heads", "audit")) + "</h2><p class='lead'>" + esc(word("ui.audit_lead")) +
      "</p><p class='hash'>" + esc(word("ui.published")) + " · " + esc(m.audit.head) + "</p><div class='auditbar'>" + buttons + "</div>" +
      (S.tamper ? "<p class='note'>" + esc(word("ui.tamper_note", {seq: S.tamperSeq})) + "</p>" : "") + result +
      "<div class='scroll' data-keep='ledger'><table class='ledger'><thead><tr>" + ["seq", "at", "session", "actor", "action", "target", "verdict", "rule",
        "hash"].map(function (k) {
        return "<th>" + esc(cols[k] || k) + "</th>";
      }).join("") + "</tr></thead><tbody>" + rows + "</tbody></table></div></div>";
    restore(hostEl, spots);
    /* The entry the check fails at, or the one that was changed, comes into view inside the log. */
    var mark = $(".ledger tr.bad", hostEl) || $(".ledger tr.changed", hostEl);
    if (mark && mark.scrollIntoView && !hostEl.hidden) { mark.scrollIntoView({block: "center", behavior: calm() ? "auto" : "smooth"}); }
  }

  /* ------------------------------------------------------------------ the code view */
  function loadCode() {
    if (win.ACCODE) { codeTree(); return; }
    if (S.codeLoading || !doc.body) { return; }
    S.codeLoading = true;
    var s = doc.createElement("script");
    s.src = "code.js";
    s.onload = codeTree;
    doc.body.appendChild(s);
  }
  function codeTree() {
    var tree = $("#code-tree"), code = win.ACCODE;
    if (!tree || !code) { return; }
    var folder = null, out = "";
    Object.keys(code.files).sort().forEach(function (rel) {
      var top = rel.indexOf("/") >= 0 ? rel.split("/")[0] + "/" : "";
      if (top !== folder) { folder = top; if (top) { out += "<p>" + esc(top) + "</p>"; } }
      out += "<button type='button' data-file='" + esc(rel) + "'>" + esc(rel.slice(top.length)) + "</button>";
    });
    tree.innerHTML = out;
    openFile(S.codeFile || code.default);
  }
  function openFile(rel) {
    var code = win.ACCODE;
    S.codeFile = rel;
    if (!code || !code.files[rel]) { return; }
    $("#code-path").textContent = rel;
    $("#code-body").textContent = code.files[rel];
    $$("#code-tree button, .cfeat").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-file") === rel); });
  }

  /* ------------------------------------------------------------------ views and the address */
  function render() {
    if (S.view === "trace") { renderTrace(); }
    if (S.view === "session") { renderSession(); }
    if (S.view === "policies") { renderPolicies(); }
    if (S.view === "audit") { renderAudit(); }
  }
  function setView(v, keepHash) {
    if (VIEWS.indexOf(v) < 0) { return; }
    S.view = v;
    VIEWS.forEach(function (name) {
      var el = $("#v-" + name);
      if (el) { el.hidden = name !== v; }
      if (doc.body) { doc.body.classList.toggle("view-" + name, name === v); }
    });
    $$("[data-view]").forEach(function (b) {
      var on = b.getAttribute("data-view") === v;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    if (v === "how") { loadCode(); }
    render();
    if (!keepHash) { writeHash(); }
  }
  ACP.setView = setView;
  function writeHash() {
    if (S.tour || !win.history || !win.history.replaceState) { return; }
    var h = "#" + S.view + (S.view === "trace" && S.sel ? "/" + S.sel : S.view === "session" && S.job ? "/" + S.job : "");
    win.history.replaceState(null, "", h);
  }
  function readHash() {
    var h = String((win.location || {}).hash || "").replace(/^#/, ""), parts = h.split("/");
    if (parts[0] === "tour") { tour(Number(parts[1]) || 1); return; }
    if (parts[0] === "trace" && parts[1] && find(parts[1])) { S.sel = parts[1]; }
    if (parts[0] === "session" && parts[1] && lane(parts[1])) { S.job = parts[1]; }
    setView(VIEWS.indexOf(parts[0]) >= 0 ? parts[0] : "trace", true);
  }
  function setModel(id) {
    if (!(AC.mornings || {})[id]) { return; }
    S.model = id;
    S.sel = defaultSel();
    S.chain = null;
    S.tamper = 0;
    S.result = null;
    S.answers = {};
    render();
    writeHash();
  }
  ACP.setModel = setModel;

  /* ------------------------------------------------------------------ the tour */
  var STEPS = [
    {view: "trace", focus: "#trace"},
    {view: "trace", sel: "quarantine", focus: "#trace"},
    {view: "trace", sel: "quarantine", focus: "#detail"},
    {view: "trace", sel: "stop", focus: "#detail"},
    {view: "trace", sel: "wait", focus: "#detail"},
    {view: "session", job: "billing-export", focus: ".term"},
    {view: "policies", focus: "#rules"},
    {view: "audit", focus: ".audit"},
    {view: "how", focus: ".how"}
  ];
  ACP.steps = STEPS.length;
  function selByClass(cls) {
    var ls = lanes();
    for (var i = 0; i < ls.length; i++) {
      var e = ls[i].events.filter(function (x) { var m = markOf(x); return m && m.cls === cls; })[0];
      if (e) { return key(ls[i], e); }
    }
    return null;
  }
  function tour(n) {
    if (!n || n > STEPS.length) { endTour(); return; }
    var st = STEPS[n - 1];
    S.tour = n;
    if (st.job && lane(st.job)) { S.job = st.job; }
    if (st.sel) { S.sel = selByClass(st.sel) || S.sel; }
    setView(st.view, true);
    if (win.history && win.history.replaceState) { win.history.replaceState(null, "", "#tour/" + n); }
    drawTour();
  }
  ACP.tour = tour;
  function endTour() {
    S.tour = 0;
    var svg = $("#tour"), boxEl = $("#tour-box");
    if (svg) { svg.hidden = true; }
    if (boxEl) { boxEl.hidden = true; }
    writeHash();
  }
  function drawTour() {
    var st = STEPS[S.tour - 1], svg = $("#tour"), boxEl = $("#tour-box"), focus = st ? $(st.focus) : null;
    if (!svg || !boxEl || !focus) { return; }
    var W = win.innerWidth || 1600, H = win.innerHeight || 1000, pad = 8, r = focus.getBoundingClientRect();
    /* Bring the step into view first, without the smooth scroll, so the hole and the box are measured where they land. */
    if (focus.scrollIntoView && (r.top < 64 || r.bottom > H)) {
      focus.scrollIntoView({block: r.height > H - 120 ? "start" : "center", behavior: "instant"});
      r = focus.getBoundingClientRect();
    }
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.innerHTML = "<defs><mask id='tour-cut' maskUnits='userSpaceOnUse'><rect fill='#fff' x='0' y='0' width='" + W + "' height='" + H +
      "'/><rect class='hole' rx='12' fill='#000' x='" + (r.left - pad) + "' y='" + (r.top - pad) + "' width='" + (r.width + pad * 2) +
      "' height='" + (r.height + pad * 2) + "'/></mask></defs><rect class='shade' x='0' y='0' width='" + W + "' height='" + H +
      "' mask='url(#tour-cut)'/>";
    svg.hidden = false;
    boxEl.innerHTML = "<p class='tcount'>" + esc(word("ui.tour_count", {n: S.tour, total: STEPS.length})) + "</p><p>" +
      esc(tab("ui.tour", String(S.tour))) + "</p><div class='tnav'><button type='button' class='link' data-tour='close'>" +
      esc(word("ui.tour_close")) + "</button>" + (S.tour > 1 ? "<button type='button' class='btn ghost' data-tour='back'>" +
      esc(word("ui.tour_back")) + "</button>" : "") + "<button type='button' class='btn' data-tour='next'>" + esc(word("ui.tour_next")) +
      "</button></div>";
    boxEl.hidden = false;
    /* The box goes below the step when it fits, then above it, then beside a narrow step, and otherwise inside the step's
       lower right corner. A step as wide as the window gets the box at its right, where the lanes run out. */
    var h = boxEl.offsetHeight || 200, w = boxEl.offsetWidth || 340, wide = r.width > W * 0.6, top, left = wide ? r.right - w : r.left;
    if (r.bottom + 16 + h <= H - 12) { top = r.bottom + 16; }
    else if (r.top - 16 - h >= 72) { top = r.top - 16 - h; }
    else if (!wide && r.right + 16 + w <= W - 12) { top = r.top + 24; left = r.right + 16; }
    else { top = Math.min(H - 12, r.bottom) - h - 16; left = r.right - w - 16; }
    boxEl.style.top = Math.max(12, top) + "px";
    boxEl.style.left = Math.max(12, Math.min(W - w - 12, left)) + "px";
  }

  /* ------------------------------------------------------------------ events */
  doc.addEventListener("click", function (ev) {
    var t = ev.target, el;
    if (!t || !t.closest) { return; }
    if ((el = t.closest("[data-tour]"))) {
      var a = el.getAttribute("data-tour");
      if (a === "next") { tour(S.tour + 1); } else if (a === "back") { tour(S.tour - 1); } else { endTour(); }
      return;
    }
    if ((el = t.closest("#tour-start"))) { tour(1); return; }
    if ((el = t.closest("#theme"))) { setDark(!doc.body.classList.contains("dark")); return; }
    /* The brand is the way home: the morning, with the event a fresh load opens on. */
    if ((el = t.closest("[data-home]"))) {
      if (ev.preventDefault) { ev.preventDefault(); }
      if (S.tour) { endTour(); }
      S.sel = defaultSel();
      setView("trace");
      return;
    }
    if ((el = t.closest("#replay"))) { startReplay(); return; }
    if ((el = t.closest("[data-answer]"))) { answer(el.getAttribute("data-job"), el.getAttribute("data-answer")); return; }
    if ((el = t.closest("[data-pick]"))) { pick(el.getAttribute("data-pick")); return; }
    if ((el = t.closest("[data-step]"))) { if (!el.hasAttribute("disabled")) { stepSel(Number(el.getAttribute("data-step"))); } return; }
    if ((el = t.closest("[data-out]"))) { var k = el.getAttribute("data-out"); S.open[k] = !S.open[k]; renderSession(); return; }
    if ((el = t.closest(".mk, .tk")) && S.view === "trace") { select(el.getAttribute("data-ev")); return; }
    if ((el = t.closest("[data-lane]"))) { S.job = el.getAttribute("data-lane"); setView("session"); return; }
    if ((el = t.closest("[data-session]"))) { S.job = el.getAttribute("data-session"); S.term = null; renderSession(); writeHash(); return; }
    if ((el = t.closest("[data-poljob]"))) { S.polJob = el.getAttribute("data-poljob"); renderPolicies(); return; }
    if ((el = t.closest("[data-rule]"))) { setRule(el.getAttribute("data-rule"), el.getAttribute("data-verdict")); return; }
    if ((el = t.closest("#reset-policy"))) { S.policy = clone(AC.policy); renderPolicies(); return; }
    if ((el = t.closest("[data-audit]"))) { if (!el.hasAttribute("disabled")) { tamper(el.getAttribute("data-audit")); } return; }
    if ((el = t.closest("[data-file]"))) { openFile(el.getAttribute("data-file")); return; }
    if ((el = t.closest("[data-view]"))) { setView(el.getAttribute("data-view")); }
  });
  doc.addEventListener("change", function (ev) {
    if (ev.target && ev.target.id === "model") { setModel(ev.target.value); }
  });
  /* Hovering or focusing a tile or a turn shows what it was. */
  doc.addEventListener("mouseover", function (ev) { var el = tipTarget(ev.target); if (el) { showTip(el); } });
  doc.addEventListener("mouseout", function (ev) {
    var el = tipTarget(ev.target);
    if (el && !(ev.relatedTarget && el.contains && el.contains(ev.relatedTarget))) { hideTip(); }
  });
  doc.addEventListener("focusin", function (ev) { var el = tipTarget(ev.target); if (el) { showTip(el); } else { hideTip(); } });
  doc.addEventListener("focusout", function () { hideTip(); });
  /* Arrow keys move along a lane's marks and between lanes, and Escape closes the tour. */
  doc.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && S.tour) { endTour(); return; }
    if (S.tour && (ev.key === "ArrowRight" || ev.key === "ArrowLeft")) { tour(S.tour + (ev.key === "ArrowRight" ? 1 : -1)); return; }
    var t = ev.target;
    if (!t || !t.getAttribute || !t.getAttribute("data-ev") || S.view !== "trace") { return; }
    var f = find(t.getAttribute("data-ev"));
    if (!f) { return; }
    var shown = f.lane.events.filter(function (e) { return markOf(e) || isCall(e); }), i = shown.indexOf(f.e), ls = lanes(), li = ls.indexOf(f.lane);
    var target = null;
    if (ev.key === "ArrowRight" && i < shown.length - 1) { target = key(f.lane, shown[i + 1]); }
    if (ev.key === "ArrowLeft" && i > 0) { target = key(f.lane, shown[i - 1]); }
    if ((ev.key === "ArrowDown" || ev.key === "ArrowUp") && ls[li + (ev.key === "ArrowDown" ? 1 : -1)]) {
      var other = ls[li + (ev.key === "ArrowDown" ? 1 : -1)], near = other.events.filter(function (e) { return markOf(e) || isCall(e); });
      near.sort(function (a, b) { return Math.abs(a.at_ms - f.e.at_ms) - Math.abs(b.at_ms - f.e.at_ms); });
      if (near[0]) { target = key(other, near[0]); }
    }
    if (target) { if (ev.preventDefault) { ev.preventDefault(); } select(target, true); }
  });
  /* On a phone the three main views sit behind the tab bar, and a sideways swipe moves between them. */
  var touch = {x: null};
  doc.addEventListener("touchstart", function (ev) { touch.x = ev.touches && ev.touches[0] ? ev.touches[0].clientX : null; });
  doc.addEventListener("touchend", function (ev) {
    var end = ev.changedTouches && ev.changedTouches[0] ? ev.changedTouches[0].clientX : null;
    if (touch.x === null || end === null || !phone() || S.tour) { return; }
    var i = SCREENS.indexOf(S.view), dx = end - touch.x;
    if (i >= 0 && Math.abs(dx) > 70) { setView(SCREENS[Math.max(0, Math.min(SCREENS.length - 1, i + (dx < 0 ? 1 : -1)))]); }
    touch.x = null;
  });
  if (win.addEventListener) {
    win.addEventListener("hashchange", function () { if (!S.tour) { readHash(); } });
    win.addEventListener("resize", function () { drawThread(false); if (S.tour) { drawTour(); } });
  }
  /* A column of the inspector scrolling on its own moves the thread's ends, so it's drawn again where they are. */
  doc.addEventListener("scroll", function (ev) {
    var t = ev.target;
    if (t && t.closest && t.closest("#detail")) { drawThread(false); }
    hideTip();
  }, true);

  /* ------------------------------------------------------------------ start */
  ACP.state = function () {
    return {view: S.view, model: S.model, sel: S.sel, job: S.job, polJob: S.polJob, answers: clone(S.answers), tamper: S.tamper,
      chain: chain().length, tour: S.tour, replaying: S.replaying};
  };
  function start() {
    var pick = $("#model");
    if (pick) {
      pick.innerHTML = (AC.models || []).map(function (m) {
        return "<option value='" + esc(m.id) + "'" + (m.id === S.model ? " selected" : "") + ">" + esc(m.label) + "</option>";
      }).join("");
    }
    S.sel = defaultSel();
    readHash();
    /* The quarantine's thread is measured from the text, so it's drawn again once the page's own fonts are in. */
    if (doc.fonts && doc.fonts.ready && doc.fonts.ready.then) { doc.fonts.ready.then(function () { drawThread(false); if (S.tour) { drawTour(); } }); }
  }
  start();
})();
