/* The console's policy in the visitor's browser: the same decision engine/policy.py makes, on the same recorded facts.
   Rules are read top to bottom and the first one that matches decides, and a call no rule matches gets the policy's
   "unmatched" verdict. tests/js/check_policy.js runs it on every vector engine/policy.py wrote and stops on the first
   disagreement. A classic script with no dependencies, so it runs from file:// and under node. */
(function (root) {
  "use strict";
  var UNMATCHED = "no-rule";
  var VIRTUAL = "/workspace";

  function escapeChar(c) { return /[\\^$.*+?()[\]{}|\/-]/.test(c) ? "\\" + c : c; }

  /* Whole-text match where * matches any run of characters. With slash, * stops at a slash and ** doesn't. */
  function glob(pattern, text, slash) {
    var out = "", i = 0;
    while (i < pattern.length) {
      if (slash && pattern.substr(i, 2) === "**") { out += "[\\s\\S]*"; i += 2; }
      else if (pattern[i] === "*") { out += slash ? "[^/]*" : "[\\s\\S]*"; i += 1; }
      else { out += escapeChar(pattern[i]); i += 1; }
    }
    return new RegExp("^(?:" + out + ")$").test(text);
  }

  function pathMatch(pattern, path) {
    if (pattern.indexOf("/") < 0) {
      var parts = path.replace(/\/+$/, "").split("/");
      return glob(pattern, parts[parts.length - 1], true);
    }
    var rel = (path === VIRTUAL || path.indexOf(VIRTUAL + "/") === 0) ? path.slice(VIRTUAL.length + 1) : path.replace(/^\/+/, "");
    return glob(pattern, rel, true);
  }

  function words(pat, ws) {
    if (!pat.length) { return !ws.length; }
    if (pat[0] === "*") {
      for (var i = 0; i <= ws.length; i++) { if (words(pat.slice(1), ws.slice(i))) { return true; } }
      return false;
    }
    return ws.length > 0 && glob(pat[0], ws[0], false) && words(pat.slice(1), ws.slice(1));
  }

  function commandMatch(pattern, argv) { return words(pattern.split(/ +/).filter(Boolean), argv.slice()); }

  function matches(rule, f) {
    if (rule.tools && rule.tools.indexOf(f.tool) < 0) { return false; }
    if ("outside" in rule && !!f.outside !== !!rule.outside) { return false; }
    if (rule.paths) {
      var paths = f.paths || [], hit = false;
      for (var a = 0; a < rule.paths.length && !hit; a++) {
        for (var b = 0; b < paths.length && !hit; b++) { hit = pathMatch(rule.paths[a], paths[b]); }
      }
      if (!hit) { return false; }
    }
    if (rule.commands) {
      var argv = f.argv || [];
      if (!argv.length || !rule.commands.some(function (c) { return commandMatch(c, argv); })) { return false; }
    }
    if ("operators" in rule && !!f.operators !== !!rule.operators) { return false; }
    if (rule.hosts) {
      var host = (f.host || "").toLowerCase();
      if (!host || !rule.hosts.some(function (h) { return glob(h.toLowerCase(), host, false); })) { return false; }
    }
    if ("max_bytes" in rule && !((f.bytes || 0) > rule.max_bytes)) { return false; }
    if ("max_query" in rule && !((f.query_len || 0) > rule.max_query)) { return false; }
    return true;
  }

  function decide(facts, policy) {
    for (var i = 0; i < policy.rules.length; i++) {
      var rule = policy.rules[i];
      if (matches(rule, facts)) {
        return {verdict: rule.verdict, rule: rule.id, stop: !!rule.stop && rule.verdict === "deny"};
      }
    }
    return {verdict: policy.unmatched || "deny", rule: UNMATCHED, stop: false};
  }

  var api = {decide: decide, matches: matches, glob: glob, pathMatch: pathMatch, commandMatch: commandMatch, UNMATCHED: UNMATCHED};
  if (typeof module !== "undefined" && module.exports) { module.exports = api; } else { root.ACPolicy = api; }
})(this);
