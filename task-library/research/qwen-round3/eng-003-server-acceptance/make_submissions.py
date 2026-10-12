#!/usr/bin/env python3
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
CAL = os.path.abspath(os.path.join(HERE, "..", "..", "..", "calibration", "eng-003-resource-manager", "private"))
SUBS = os.path.join(HERE, "submissions")

BAD_ROUTE_SERVER = '''#!/usr/bin/env python3
"""Negative fixture: GET /resources succeeds, but POST /resources incorrectly returns 404."""
import argparse, json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, obj, ctype="application/json"):
        b = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", ctype+"; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path.startswith("/resources"):
            return self._send(200, {"ok": True, "resources": []})  # Minimal fixture supports only the resource-list endpoint.
        return self._send(404, {"ok": False})
    def do_POST(self):
        return self._send(404, {"ok": False, "error": "not_found"})  # BUG: This fixture intentionally omits the POST route.

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--store", required=True)
    ap.add_argument("--port", type=int, default=8000); ap.add_argument("--frontend", default=None)
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    print(f"serving on http://127.0.0.1:{srv.server_address[1]}")
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    finally: srv.server_close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def build_good():
    d = os.path.join(SUBS, "good_submission")
    if os.path.exists(d):
        shutil.rmtree(d)
    write(os.path.join(d, "service.py"), read(os.path.join(CAL, "ref_store.py")))
    srv = read(os.path.join(CAL, "ref_server.py")).replace("ref_store", "service")
    write(os.path.join(d, "server.py"), srv)
    fe = os.path.join(CAL, "frontend")
    for fn in os.listdir(fe):
        write(os.path.join(d, "frontend", fn), read(os.path.join(fe, fn)))
    return d


def build_missing_server():
    d = os.path.join(SUBS, "bad_server_missing")
    if os.path.exists(d):
        shutil.rmtree(d)
    write(os.path.join(d, "service.py"), read(os.path.join(CAL, "ref_store.py")))  # Internal calibration detail.
    return d


def build_wrong_route():
    d = os.path.join(SUBS, "bad_server_wrong_route")
    if os.path.exists(d):
        shutil.rmtree(d)
    write(os.path.join(d, "service.py"), read(os.path.join(CAL, "ref_store.py")))
    write(os.path.join(d, "server.py"), BAD_ROUTE_SERVER)
    return d


if __name__ == "__main__":
    print("CAL =", CAL, "exists:", os.path.isdir(CAL))
    for b in (build_good, build_missing_server, build_wrong_route):
        print("built:", os.path.relpath(b(), HERE))
