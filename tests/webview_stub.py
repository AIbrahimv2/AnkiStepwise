"""A stand-in for Anki's media server, so the real Stepwise window (its
AnkiWebView and the built page) can load offscreen. Imported by the tests
that open the window."""
import os
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from harness import SRC, app, mw, ui

PORT = 0  # any free port
PAGES = {}
ANKI_WEB = "/Applications/Anki.app/Contents/Resources/app_packages/_aqt/data/web"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/_anki/legacyPageData":
            pid = self.path.split("id=")[-1]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(PAGES.get(pid, "").encode())
            return
        if path.startswith("/_anki/"):
            f = os.path.join(ANKI_WEB, path[len("/_anki/"):])
            if os.path.isfile(f):
                self.send_response(200)
                self.send_header("Content-Type", "text/css" if f.endswith(".css") else "application/javascript")
                self.end_headers()
                self.wfile.write(open(f, "rb").read())
                return
        prefix = "/_addons/tq/web/"
        if path.startswith(prefix):
            f = os.path.join(SRC, "web", path[len(prefix):])
            if os.path.isfile(f):
                self.send_response(200)
                self.send_header("Content-Type", "text/css" if f.endswith(".css") else "application/javascript")
                self.end_headers()
                self.wfile.write(open(f, "rb").read())
                return
        self.send_response(404)
        self.end_headers()


srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
mw.mediaServer = types.SimpleNamespace(
    getPort=lambda: PORT, set_page_html=lambda pid, html, ctx: PAGES.__setitem__(str(pid), html))
mw.app = app
mw.serverURL = lambda: f"http://127.0.0.1:{PORT}/"
mw.baseHTML = lambda: f'<base href="http://127.0.0.1:{PORT}/">'
mw.pm = types.SimpleNamespace(minimalist_mode=lambda: False, reduce_motion=lambda: False)

ui.restoreGeom = ui.saveGeom = lambda *a, **k: None
