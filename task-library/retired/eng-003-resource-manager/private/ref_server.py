#!/usr/bin/env python3
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ref_store import ResourceStore  # noqa: E402

FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")


def make_handler(store, frontend_dir):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, obj, ctype="application/json"):
            body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(n).decode("utf-8") if n else "{}"
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path == "/resources":
                return self._send(200, {"ok": True, "resources": store.list(q.get("tag", [None])[0], q.get("text", [None])[0])})
            if u.path.startswith("/resources/"):
                r = store.get(u.path.rsplit("/", 1)[1])
                return self._send(200 if r["ok"] else 404, r)
            if u.path == "/export":
                fmt = q.get("fmt", ["json"])[0]
                return self._send(200, store.export(fmt), "text/plain")
            
            rel = "index.html" if u.path in ("/", "") else u.path.lstrip("/")
            fp = os.path.join(frontend_dir, rel.replace("/", os.sep))
            if os.path.isfile(fp):
                ctype = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}.get(os.path.splitext(fp)[1], "application/octet-stream")
                with open(fp, "rb") as f:
                    return self._send(200, f.read(), ctype)
            return self._send(404, {"ok": False, "error": "not_found"})

        def do_POST(self):
            u = urlparse(self.path)
            data = self._read_json()
            if data is None:
                return self._send(400, {"ok": False, "errors": [{"code": "bad_json"}]})
            if u.path == "/resources":
                r = store.add(data.get("title"), data.get("url"), data.get("tags"), data.get("notes"))
                return self._send(201 if r["ok"] else 400, r)
            if u.path == "/import":
                r = store.import_data(data.get("payload", ""), data.get("fmt", "json"), data.get("mode", "merge"))
                return self._send(200 if r["ok"] else 400, r)
            return self._send(404, {"ok": False, "error": "not_found"})

        def do_PUT(self):
            u = urlparse(self.path)
            if u.path.startswith("/resources/"):
                data = self._read_json() or {}
                r = store.edit(u.path.rsplit("/", 1)[1], data.get("title"), data.get("url"), data.get("tags"), data.get("notes"))
                return self._send(200 if r["ok"] else (404 if any(e.get("code") == "not_found" for e in r.get("errors", [])) else 400), r)
            return self._send(404, {"ok": False, "error": "not_found"})

        def do_DELETE(self):
            u = urlparse(self.path)
            if u.path.startswith("/resources/"):
                r = store.delete(u.path.rsplit("/", 1)[1])
                return self._send(200 if r["ok"] else 404, r)
            return self._send(404, {"ok": False, "error": "not_found"})

    return H


def build_server(store, port=0, frontend_dir=FRONTEND):
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(store, frontend_dir))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--frontend", default=FRONTEND)
    a = ap.parse_args(argv)
    store = ResourceStore(a.store)
    srv = build_server(store, a.port, a.frontend)
    print(f"serving on http://127.0.0.1:{srv.server_address[1]} store={a.store}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
