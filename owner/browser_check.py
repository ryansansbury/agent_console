"""The owner's machine only. Look at the page in real Chrome: screenshots, the line rule, overlaps, console errors and
network requests.

    bash owner/screenshots.sh            (from the build folder)

It opens the built page in headless Chrome with a fresh profile and drives it over the DevTools pipe, from the file
system and once from a small server on 127.0.0.1 at a free port. Everything goes to owner/out/, which is gitignored:

    screens/card-1600.png           the page as a fresh load opens it at 1600 by 1000, the homepage card
    screens/card-1600-replay.png    the same frame partway through the replay
    screens/<width>-<view>.png      every view at 1440 and 1280 (the trace, a session, the policy, the audit log and How
                                    it works), full height
    screens/1440-<state>.png        the denial and the waiting push selected, the push approved, a rule changed in the
                                    simulator, an old audit entry changed, and the billing and infra terminals
    screens/1440-tour-<n>.png       every tour step
    screens/<768|390>-<view>.png    a tablet and a phone, every view
    screens/gallery-<name>.png      the README's gallery at 1600 by 1000, copied to docs/gallery/ after a real build
    layout.json                     last lines under 80% full, text over text, boxes that spill, anything wider than the
                                    window, a desktop page that scrolls (only the cards may), and whether the
                                    quarantine's thread drew, for each shot
    console.json, network.json      anything the page logged as an error, and every request it made
    browser_check.json              the summary this prints

Standard library only.
"""
import argparse
import base64
import functools
import http.server
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SITE = ROOT.joinpath("site")
OUT = HERE.joinpath("out")
SHOTS = OUT.joinpath("screens")
APPS = Path("/").joinpath("Applications")
CHROMES = (APPS.joinpath("Google Chrome.app", "Contents", "MacOS", "Google Chrome"),
           APPS.joinpath("Chromium.app", "Contents", "MacOS", "Chromium"))
WIDE = ((1440, 900), (1280, 800))
SMALL = ((768, 1024), (390, 844))
VIEWS = ("trace", "session", "policies", "audit", "how")
SETTLE = 1.2
TRAMPOLINE = 'exec "$@" 3<&0 4>&1 0</dev/null 1>&2'
THREAD_JS = ("(function () { var p = document.querySelectorAll('#detail .threads path'); var bad = 0; "
             "p.forEach(function (x) { if (/NaN/.test(x.getAttribute('d'))) { bad += 1; } }); "
             "return {threads: p.length, bad: bad}; })()")
LAYOUT_JS = """(function () {
  var W = window.innerWidth, out = {wider_than_window: document.documentElement.scrollWidth > W + 1, overlaps: [],
    short_last_lines: [], spills: []};
  // On a desktop the page is one screen: neither the page nor the view under the top bar may scroll, only the cards.
  var main = document.querySelector('main');
  out.page_scrolls = W > 900 && (document.documentElement.scrollHeight > window.innerHeight + 1 ||
    !!(main && main.scrollHeight > main.clientHeight + 1));
  var root = document.body, boxes = new Map(), covers = [];
  function name(el) {
    return (el.id ? '#' + el.id : el.tagName.toLowerCase() + Array.prototype.map.call(el.classList, function (c) {
      return '.' + c; }).join('')).slice(0, 50);
  }
  function clip(el) {
    if (boxes.has(el)) { return boxes.get(el); }
    var b = {l: -1e9, t: -1e9, r: 1e9, b: 1e9};
    for (var a = el; a && a !== document.documentElement; a = a.parentElement) {
      var cs = getComputedStyle(a);
      if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
        var q = a.getBoundingClientRect();
        b = {l: Math.max(b.l, q.left), t: Math.max(b.t, q.top), r: Math.min(b.r, q.right), b: Math.min(b.b, q.bottom)};
      }
    }
    boxes.set(el, b);
    return b;
  }
  root.querySelectorAll('*').forEach(function (el) {
    if (el.closest('svg') || !el.checkVisibility()) { return; }
    var cs = getComputedStyle(el);
    if (cs.position === 'sticky' || cs.position === 'fixed') { covers.push(el); }
    if (out.spills.length >= 25 || el.closest('pre, #code-tree, .tbody, .scroll') || cs.display === 'inline' || !el.clientWidth) { return; }
    if (el.scrollWidth > el.clientWidth + 1) {
      var scrolls = cs.overflowX === 'auto' || cs.overflowX === 'scroll';
      if (!scrolls) { out.spills.push(name(el) + ' by ' + (el.scrollWidth - el.clientWidth) + 'px'); }
    }
  });
  function covered(el, f) {
    return covers.some(function (c) {
      if (c === el || c.contains(el)) { return false; }
      var q = c.getBoundingClientRect();
      return f.l < q.right && f.r > q.left && f.t < q.bottom && f.b > q.top;
    });
  }
  root.querySelectorAll('p, li, h2, h3').forEach(function (el) {
    if (el.closest('pre, #code-tree, .tbody, .page, .why, .evlist, .risk, .chain, .verdict, .tcount') || !el.checkVisibility() ||
        el.querySelector('button, select, code')) { return; }
    var r = document.createRange(); r.selectNodeContents(el);
    var rects = Array.prototype.filter.call(r.getClientRects(), function (x) { return x.width > 1; });
    if (rects.length < 2) { return; }
    var tops = {}, box = el.getBoundingClientRect();
    rects.forEach(function (x) { var k = Math.round(x.top); tops[k] = Math.max(tops[k] || 0, x.right); });
    var keys = Object.keys(tops).map(Number).sort(function (a, b) { return a - b; });
    if (keys.length < 2) { return; }
    var fill = (tops[keys[keys.length - 1]] - box.left) / Math.max(1, box.width);
    if (fill < 0.8) { out.short_last_lines.push({text: el.textContent.trim().slice(-60), fill: Math.round(fill * 100)}); }
  });
  var frags = [], walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), node, range = document.createRange();
  while ((node = walker.nextNode())) {
    var el = node.parentElement;
    if (!/\\S/.test(node.data) || !el || el.closest('script, style, pre, #code-tree, .mk') || !el.checkVisibility()) { continue; }
    var box = clip(el);
    range.selectNodeContents(node);
    Array.prototype.forEach.call(range.getClientRects(), function (x) {
      if (x.width < 1 || x.height < 1) { return; }
      var h = x.bottom - x.top, mid = (x.top + x.bottom) / 2;
      var f = {el: el, l: Math.max(x.left, box.l), r: Math.min(x.right, box.r), t: x.top + h * 0.2, b: x.bottom - h * 0.2,
        text: node.data.trim().slice(0, 40)};
      if (mid < box.t || mid > box.b || f.r - f.l < 1 || covered(el, f)) { return; }
      frags.push(f);
    });
  }
  frags.sort(function (a, b) { return a.t - b.t; });
  for (var i = 0; i < frags.length && out.overlaps.length < 20; i++) {
    for (var j = i + 1; j < frags.length && frags[j].t < frags[i].b; j++) {
      var f = frags[i], g = frags[j];
      if (f.el === g.el || f.el.contains(g.el) || g.el.contains(f.el)) { continue; }
      if (Math.min(f.r, g.r) - Math.max(f.l, g.l) > 2) { out.overlaps.push(f.text + ' / ' + g.text); }
    }
  }
  return out;
})()"""


def find_chrome(given=None):
    if given:
        return str(given)
    for p in CHROMES:
        if p.exists():
            return str(p)
    for n in ("google-chrome", "chromium"):
        if shutil.which(n):
            return shutil.which(n)
    raise SystemExit("Chrome wasn't found. Run again with --chrome and the path to the Chrome program.")


class CDP:
    """The DevTools protocol over Chrome's pipe: JSON messages, each ended by a zero byte."""

    def __init__(self, proc, on_event=None):
        self.proc, self.on_event = proc, on_event
        self.next_id, self.responses, self.events = 0, {}, []
        self.cond, self.wlock = threading.Condition(), threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        buf = b""
        while True:
            chunk = self.proc.stdout.read1(1 << 16)
            if not chunk:
                break
            buf += chunk
            while b"\0" in buf:
                raw, buf = buf.split(b"\0", 1)
                msg = json.loads(raw)
                with self.cond:
                    if "id" in msg:
                        self.responses[msg["id"]] = msg
                    else:
                        self.events.append(msg)
                    self.cond.notify_all()
                if "id" not in msg and self.on_event:
                    self.on_event(msg)

    def send(self, method, params=None, session=None, timeout=60):
        with self.cond:
            self.next_id += 1
            mid = self.next_id
        msg = {"id": mid, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        with self.wlock:
            self.proc.stdin.write(json.dumps(msg).encode() + b"\0")
            self.proc.stdin.flush()
        deadline = time.time() + timeout
        with self.cond:
            while mid not in self.responses:
                left = deadline - time.time()
                if left <= 0:
                    raise TimeoutError(method)
                self.cond.wait(left)
            reply = self.responses.pop(mid)
        if "error" in reply:
            raise RuntimeError(f"{method}: {reply['error'].get('message')}")
        return reply.get("result", {})

    def mark(self):
        with self.cond:
            return len(self.events)

    def wait_event(self, method, session, since, timeout=60):
        deadline = time.time() + timeout
        with self.cond:
            while True:
                for e in self.events[since:]:
                    if e.get("method") == method and e.get("sessionId") == session:
                        return e
                left = deadline - time.time()
                if left <= 0:
                    raise TimeoutError(method)
                self.cond.wait(left)


class Browser:
    def __init__(self, chrome):
        self.requests, self.console, self.loads = [], [], 0
        profile = OUT.joinpath("chrome-profile")
        shutil.rmtree(profile, ignore_errors=True)
        flags = ["--headless=new", "--remote-debugging-pipe", f"--user-data-dir={profile}", "--no-first-run",
                 "--no-default-browser-check", "--disable-extensions", "--hide-scrollbars", "--mute-audio",
                 "--disable-background-networking", "--disable-sync", "--disable-component-update",
                 "--allow-file-access-from-files"]
        self.log = OUT.joinpath("chrome.log").open("wb")
        self.proc = subprocess.Popen(["bash", "-c", TRAMPOLINE, "chrome", chrome, *flags], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.log)
        self.cdp = CDP(self.proc, self.event)
        target = self.cdp.send("Target.createTarget", {"url": "about:blank"})["targetId"]
        self.s = self.cdp.send("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        for m in ("Page.enable", "Runtime.enable", "Network.enable", "Log.enable"):
            self.cdp.send(m, session=self.s)
        self.size = (1600, 1000, False)

    def event(self, e):
        m, p = e.get("method"), e.get("params", {})
        if m == "Network.requestWillBeSent":
            self.requests.append(p["request"]["url"])
        elif m == "Runtime.exceptionThrown":
            d = p["exceptionDetails"]
            self.console.append({"kind": "exception", "text": (d.get("exception") or {}).get("description") or d.get("text")})
        elif m == "Runtime.consoleAPICalled" and p.get("type") in ("error", "assert"):
            self.console.append({"kind": "console.error", "text": " ".join(str(a.get("value", a.get("description")))
                                                                           for a in p.get("args", []))})
        elif m == "Log.entryAdded" and p["entry"].get("level") == "error":
            self.console.append({"kind": "log", "text": p["entry"].get("text"), "url": p["entry"].get("url")})

    def view(self, width, height, mobile=False):
        self.size = (width, height, mobile)
        self.cdp.send("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1,
                                                             "mobile": mobile}, self.s)

    def load(self, url):
        """A fresh page at the address, with a query of its own so it's never a move within the same page."""
        self.loads += 1
        base, mark, frag = url.partition("#")
        fresh = f"{base}{'&' if '?' in base else '?'}load={self.loads}{mark}{frag}"
        since = self.cdp.mark()
        self.cdp.send("Page.navigate", {"url": fresh}, self.s)
        self.cdp.wait_event("Page.loadEventFired", self.s, since)
        self.pause(0.6)

    def js(self, expr, wait=False):
        r = self.cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": wait}, self.s)
        if "exceptionDetails" in r:
            raise RuntimeError(f"{expr[:60]}: {r['exceptionDetails'].get('text')}")
        return r.get("result", {}).get("value")

    def pause(self, seconds):
        self.js(f"new Promise(r => requestAnimationFrame(() => setTimeout(r, {int(seconds * 1000)})))", wait=True)

    def shot(self, name, full=True):
        """A screenshot. A full one resizes the window to the page's height first (capturing past the window distorted
        an earlier project's shots), then puts the window back."""
        width, height, mobile = self.size
        if full:
            tall = int(self.js("Math.ceil(document.documentElement.scrollHeight)") or height)
            self.view(width, min(max(tall, height), 9000), mobile)
            self.pause(0.4)
        data = self.cdp.send("Page.captureScreenshot", {"format": "png"}, self.s, timeout=120)["data"]
        SHOTS.joinpath(f"{name}.png").write_bytes(base64.b64decode(data))
        if full:
            self.view(width, height, mobile)

    def close(self):
        try:
            self.cdp.send("Browser.close", timeout=10)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()


def serve(root):
    """The site on 127.0.0.1 at a free port, so the page is also checked the way a web server hands it over."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def act(b, script):
    b.js("(function () { var A = window.ACP; " + script + " })()")
    b.pause(SETTLE)


def measure(b, name, layout):
    found = b.js(LAYOUT_JS) or {}
    found["thread"] = b.js(THREAD_JS)
    layout[name] = found
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description="Look at the page in real Chrome.")
    ap.add_argument("--chrome")
    a = ap.parse_args(argv)
    SHOTS.mkdir(parents=True, exist_ok=True)
    for old in SHOTS.glob("*.png"):
        old.unlink()
    b = Browser(find_chrome(a.chrome))
    url = SITE.joinpath("index.html").as_uri()
    layout = {}
    try:
        b.view(1600, 1000)
        b.load(url)
        b.pause(SETTLE)
        measure(b, "card-1600", layout)
        b.shot("card-1600", full=False)
        b.shot("gallery-trace", full=False)
        b.js("document.getElementById('replay').click()")
        b.pause(4.5)
        b.shot("card-1600-replay", full=False)
        b.pause(9)
        act(b, "A.setView('session'); var l = document.querySelector(\"[data-session='billing-export']\"); if (l) { l.click(); }")
        b.shot("gallery-session", full=False)
        act(b, "A.setView('policies'); A.setRule('push', 'allow'); A.setRule('tests', 'deny');")
        b.shot("gallery-policies", full=False)
        act(b, "A.setView('audit'); A.tamper('1');")
        b.shot("gallery-audit", full=False)
        for width, height in WIDE:
            b.view(width, height)
            for view in VIEWS:
                b.load(f"{url}#{view}")
                b.pause(SETTLE)
                measure(b, f"{width}-{view}", layout)
                b.shot(f"{width}-{view}")
        b.view(1440, 900)
        b.load(url)
        b.pause(SETTLE)
        states = (("trace-stop", "var e = document.querySelector('.mk.stop'); if (e) { e.click(); }"),
                  ("trace-push", "var e = document.querySelector('.mk.wait'); if (e) { e.click(); }"),
                  ("trace-approved", "var e = document.querySelector(\"[data-answer='approve']\"); if (e) { e.click(); }"),
                  ("session-billing-export", "A.setView('session'); var l = document.querySelector(\"[data-session='billing-export']\"); if (l) { l.click(); }"),
                  ("session-infra-scripts", "var l = document.querySelector(\"[data-session='infra-scripts']\"); if (l) { l.click(); }"),
                  ("policies-changed", "A.setView('policies'); A.setRule('push', 'allow'); A.setRule('tests', 'deny');"),
                  ("audit-tampered", "A.setView('audit'); A.tamper('1');"))
        for name, script in states:
            act(b, script)
            measure(b, f"1440-{name}", layout)
            b.shot(f"1440-{name}")
        steps = int(b.js("window.ACP.steps") or 0)
        b.load(url)
        b.pause(SETTLE)
        for n in range(1, steps + 1):
            act(b, f"A.tour({n});")
            b.shot(f"1440-tour-{n}", full=False)
        for width, height in SMALL:
            b.view(width, height, mobile=width < 500)
            for view in VIEWS:
                b.load(f"{url}#{view}")
                b.pause(SETTLE)
                measure(b, f"{width}-{view}", layout)
                b.shot(f"{width}-{view}")
        httpd = serve(SITE)
        try:
            b.view(1440, 900)
            b.load(f"http://127.0.0.1:{httpd.server_address[1]}/index.html")
            b.pause(SETTLE)
            measure(b, "1440-served", layout)
        finally:
            httpd.shutdown()
    finally:
        b.close()
    own = (SITE.as_uri(), "http://127.0.0.1:")
    outside = [r for r in b.requests if not r.startswith(own) and not r.startswith("data:") and r != "about:blank"]
    OUT.joinpath("layout.json").write_text(json.dumps(layout, indent=1) + "\n", encoding="utf-8")
    OUT.joinpath("console.json").write_text(json.dumps(b.console, indent=1) + "\n", encoding="utf-8")
    OUT.joinpath("network.json").write_text(json.dumps({"requests": b.requests, "outside": outside}, indent=1) + "\n",
                                            encoding="utf-8")
    problems = {name: {k: v for k, v in found.items() if k != "thread" and v}
                for name, found in layout.items() if any(v for k, v in found.items() if k != "thread")}
    thread_bad = [n for n, f in layout.items() if (f.get("thread") or {}).get("bad")]
    summary = {"shots": len(list(SHOTS.glob("*.png"))), "layout_problems": problems, "console_errors": len(b.console),
               "requests_outside": outside, "thread_with_bad_numbers": thread_bad,
               "card_thread_drawn": bool((layout.get("card-1600", {}).get("thread") or {}).get("threads"))}
    OUT.joinpath("browser_check.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    # The README's gallery comes from the real build only, never the labeled preview.
    if '"preview":false' in SITE.joinpath("data.js").read_text(encoding="utf-8")[:200]:
        gallery = ROOT.joinpath("docs", "gallery")
        gallery.mkdir(exist_ok=True)
        for name in ("trace", "session", "policies", "audit"):
            shutil.copyfile(SHOTS.joinpath(f"gallery-{name}.png"), gallery.joinpath(f"{name}.png"))
    print(f"{summary['shots']} screenshots in owner/out/screens/. Layout problems in {len(problems)} shot(s), "
          f"{len(b.console)} console error(s), {len(outside)} request(s) off the page's own files, and the card's thread "
          f"{'drew' if summary['card_thread_drawn'] else 'did not draw'}.")
    return 1 if problems or b.console or outside or thread_bad else 0


if __name__ == "__main__":
    sys.exit(main())
