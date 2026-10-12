#!/usr/bin/env python3
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
            return self._send(200, {"ok": True, "resources": []})  
        return self._send(404, {"ok": False})
    def do_POST(self):
        return self._send(404, {"ok": False, "error": "not_found"})  

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
