"""The fixture server: the three vendors' pricing pages on 127.0.0.1 at a free port, chosen by the Host header, with the
names filled in. The owner's machine only.

The fetch tool maps https://<vendor host>/<path> to this server and sends the vendor's host along, so the agent's
address and the policy's facts stay the real-looking ones while nothing leaves the machine. Any other host or path
answers 404. The connection goes straight to 127.0.0.1 through http.client, which reads no proxy settings.
"""
import http.client
import http.server
import sys
import threading
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from generate import fixtures  # noqa: E402

PATHS = ("/pricing", "/pricing/")


def start(cast):
    """(the server, its port). The server runs on its own thread until shutdown()."""
    pages = {host: fixtures.page(vid, cast).encode("utf-8") for host, vid in fixtures.hosts(cast).items()}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            host = (self.headers.get("Host") or "").split(":")[0].rstrip(".").lower()
            body = pages.get(host) if urllib.parse.urlsplit(self.path).path in PATHS else None
            status = 200 if body else 404
            body = body or b"<html><body><p>Not found.</p></body></html>"
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def web_for(port, timeout=10):
    """The fetch tool's web: a GET for a fixture address, answered by the server on the port."""
    def fetch(url):
        parts = urllib.parse.urlsplit(url)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
        try:
            conn.request("GET", path, headers={"Host": parts.hostname or "", "User-Agent": "agent-console-fetch"})
            r = conn.getresponse()
            return r.status, r.read().decode("utf-8", errors="replace")
        finally:
            conn.close()
    return fetch
