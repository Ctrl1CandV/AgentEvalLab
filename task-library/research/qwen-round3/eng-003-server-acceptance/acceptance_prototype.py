#!/usr/bin/env python3
import argparse
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PY = shutil.which("python") or sys.executable
SUBS = os.path.join(HERE, "submissions")
READY_TIMEOUT = 12.0
CLOCK = None  # Internal calibration detail.


class _Tee:
    def __init__(self, path, orig):
        self.fh = open(path, "w", encoding="utf-8"); self.orig = orig
    def write(self, s):
        self.fh.write(s)
        try: self.orig.write(s)
        except Exception: self.orig.write(s.encode("ascii", "replace").decode("ascii"))
        return len(s)
    def flush(self):
        self.fh.flush()
        try: self.orig.flush()
        except Exception: pass


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def http(method, url, body=None, timeout=5):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def load_store_cls(submission):
    sp = os.path.join(submission, "service.py")
    if not os.path.isfile(sp):
        raise FileNotFoundError("submission is missing service.py")
    sys.path.insert(0, submission)
    spec = importlib.util.spec_from_file_location("sub_service_" + os.path.basename(submission), sp)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ResourceStore


def store_unit(submission):
    tmp = tempfile.mkdtemp(prefix="qwen_eng003_store_")
    try:
        cls = load_store_cls(submission)
        s = cls(os.path.join(tmp, "s.json"), clock=lambda: 1700000000.0)
        if not s.add("T", "https://t.io", ["a"], None)["ok"]:
            return False, 'valid resource was rejected'
        if s.add("", "bad", None, None)["ok"]:
            return False, 'blank title was accepted'
        if len(s.list()) != 1:
            return False, 'store returned the wrong resource count'
        payload = json.dumps({"resources": [{"title": "g", "url": "https://g.io"}, {"title": "", "url": "x"}]})
        if s.import_data(payload, "json", "merge")["ok"]:
            return False, 'invalid import was accepted'
        s2 = cls(os.path.join(tmp, "s.json"), clock=lambda: 1700000000.0)
        if len(s2.list()) != 1:
            return False, 'failed import changed persisted data'
        return True, 'store checks passed'
    except Exception as e:
        return False, f"store check raised {type(e).__name__}: {e}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def server_http(submission):
    server_py = os.path.join(submission, "server.py")
    if not os.path.isfile(server_py):
        return False, 'server.py is missing'
    tmp = tempfile.mkdtemp(prefix="qwen_eng003_http_")
    store = os.path.join(tmp, "store.json")
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    proc = None
    try:
        proc = subprocess.Popen([PY, server_py, "--store", store, "--port", str(port)],
                                cwd=submission, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace")
        # Internal calibration detail.
        ready = False
        t0 = time.time()
        while time.time() - t0 < READY_TIMEOUT:
            if proc.poll() is not None:
                return False, f"server exited before becoming ready; exit_code={proc.returncode}"
            st, _ = http("GET", base + "/resources", timeout=2)
            if st == 200:
                ready = True
                break
            time.sleep(0.2)
        if not ready:
            return False, 'server did not become ready'
        # Internal calibration detail.
        st, r = http("POST", base + "/resources", {"title": "A", "url": "https://a.io", "tags": ["x"]})
        if st != 201 or not (isinstance(r, dict) and r.get("ok")):
            return False, f"POST /resources expected HTTP 201 with ok=true; got {st} {str(r)[:60]}"
        rid = r["resource"]["id"]
        st, r = http("GET", base + "/resources")
        if st != 200 or len(r.get("resources", [])) != 1:
            return False, f"GET /resources returned an invalid resource list; status= {st}"
        st, r = http("PUT", base + f"/resources/{rid}", {"title": "A2"})
        if st != 200 or r.get("resource", {}).get("title") != "A2":
            return False, f"PUT /resources/{rid} failed; status= {st}"
        st, r = http("POST", base + "/import", {"payload": json.dumps({"resources": [{"title": "B", "url": "https://b.io"}]}), "fmt": "json", "mode": "merge"})
        if st != 200 or not r.get("ok"):
            return False, f"POST /import failed; status={st}; response={str(r)[:60]}"
        st, r = http("GET", base + "/export?fmt=json")
        if st != 200 or "resources" not in (r if isinstance(r, str) else json.dumps(r)):
            return False, f"GET /export failed; status={st}"
        st, r = http("DELETE", base + f"/resources/{rid}")
        if st != 200:
            return False, f"DELETE /resources failed; status={st}"
        return True, 'server checks passed'
    except Exception as e:
        return False, f"server check raised {type(e).__name__}: {e}"
    finally:
        # Internal calibration detail.
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        shutil.rmtree(tmp, ignore_errors=True)


def cleanup_after(submission):
    server_py = os.path.join(submission, "server.py")
    if not os.path.isfile(server_py):
        return False, 'server.py is missing'
    tmp = tempfile.mkdtemp(prefix="qwen_eng003_rel_")
    port = free_port()
    proc = subprocess.Popen([PY, server_py, "--store", os.path.join(tmp, "s.json"), "--port", str(port)],
                            cwd=submission, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < READY_TIMEOUT:
        st, _ = http("GET", f"http://127.0.0.1:{port}/resources", timeout=2)
        if st == 200:
            break
        time.sleep(0.2)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill(); proc.wait(timeout=5)
    terminated = proc.poll() is not None
    released = False
    for _ in range(15):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port)); s.close(); released = True; break
        except OSError:
            time.sleep(0.2)
    shutil.rmtree(tmp, ignore_errors=True)
    ok = terminated and released
    return ok, f"terminated={terminated}; port_released={released}"


def self_calibrate():
    logpath = os.path.join(HERE, "logs", "server-acceptance-self-calibration.log")
    os.makedirs(os.path.dirname(logpath), exist_ok=True)
    _o = sys.stdout; sys.stdout = _Tee(logpath, _o)
    allok = True
    print("Submitted server acceptance prototype")
    good = os.path.join(SUBS, "good_submission")
    su = store_unit(good); sh = server_http(good); pr = cleanup_after(good)
    print(f"[good] store_unit={su[0]} ({su[1]}) server_http={sh[0]} ({sh[1]}) cleanup={pr[0]} ({pr[1]})")
    allok &= su[0] and sh[0] and pr[0]

    miss = os.path.join(SUBS, "bad_server_missing")
    su2 = store_unit(miss); sh2 = server_http(miss)
    print(f"[bad_server_missing] store_unit={su2[0]} (store check raised) server_http={sh2[0]} ({sh2[1]})")
    allok &= su2[0] and (not sh2[0])  # Internal calibration detail.

    wr = os.path.join(SUBS, "bad_server_wrong_route")
    sh3 = server_http(wr)
    print(f"[bad_server_wrong_route] server_http={sh3[0]} ({sh3[1]})")
    allok &= (not sh3[0])

    print("Submitted server acceptance prototype")
    print("RESULT:", "PASS" if allok else "FAIL")
    sys.stdout = _o; sys.stdout.flush()
    return 0 if allok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-calibrate", action="store_true")
    ap.add_argument("--submission")
    a = ap.parse_args()
    if a.self_calibrate:
        sys.exit(self_calibrate())
    if a.submission:
        su = store_unit(a.submission); sh = server_http(a.submission)
        print("store_unit:", su); print("server_http:", sh)
        sys.exit(0 if (su[0] and sh[0]) else 1)
    ap.error("Provide --submission or --self-calibrate.")


if __name__ == "__main__":
    main()
