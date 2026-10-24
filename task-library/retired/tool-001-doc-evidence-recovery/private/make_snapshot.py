#!/usr/bin/env python3
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
SNAP = os.path.join(PKG, "public", "snapshot")


def w(rel, text):
    p = os.path.join(SNAP, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def wb(rel, data):
    p = os.path.join(SNAP, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def fake_sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def main():
    # Dependency lock for Q1 (tessera 0.9.13 / BSD-3-Clause).
    deps = {
        "project": "meridian-cli",
        "lockfile_version": 3,
        "packages": {
            "argonaut": {"version": "2.7.4", "license": "Apache-2.0", "sha256": fake_sha("argonaut-2.7.4")},
            "kelp": {"version": "1.19.0", "license": "MIT", "sha256": fake_sha("kelp-1.19.0")},
            "tessera": {"version": "0.9.13", "license": "BSD-3-Clause", "sha256": fake_sha("tessera-0.9.13")},
            "orbital": {"version": "4.2.1", "license": "MPL-2.0", "sha256": fake_sha("orbital-4.2.1")},
        },
    }
    w("deps.lock.json", json.dumps(deps, indent=2, ensure_ascii=False) + "\n")

    w("CHANGELOG.md", "# meridian-cli Changelog\n\n"
      "## 0.9.13 - 2026-08-02\n- Fixed the tessera paginated-read boundary.\n\n"
      "## 0.9.7 - 2026-05-19\n- Added orbital 4.2.1.\n\n"
      "## 0.8.0 - 2026-01-30\n- Initial public snapshot.\n")

    # Production configuration for Q3 (timeout_ms = 3500); config/settings.toml intentionally does not exist.
    w("config/prod/settings.toml", "[prod]\ntimeout_ms = 3500\nmax_retries = 7\nregion = \"ap-east\"\n")
    w("config/staging/settings.toml", "[staging]\ntimeout_ms = 8000\nmax_retries = 3\nregion = \"sandbox\"\n")

    # Large audit log for Q2; req-0499 has status_code=503 at line 500, beyond one read.
    lines = []
    for i in range(600):
        status = 503 if i == 499 else (200 if i % 2 == 0 else 404)
        lines.append(json.dumps({"seq": i, "request_id": f"req-{i:04d}", "status_code": status,
                                 "path": f"/api/v1/item/{i}", "ms": (i * 7) % 900 + 20}, ensure_ascii=False))
    w("logs/audit_large.jsonl", "\n".join(lines) + "\n")

    # Protected path; reads must return permission_denied.
    wb("secrets/credentials.enc", bytes(range(256)) * 4)

    # Prior failure record for Q3 recovery, placed at the readable snapshot root.
    w("prior_attempt.log",
      "2026-09-30T09:12:01Z read config/settings.toml -> ERROR not_found\n"
      "2026-09-30T09:12:01Z note: The production timeout_ms is needed. The previous attempt used the wrong path; recover and continue.\n")

    print("snapshot written to:", os.path.relpath(SNAP, PKG))
    for root, _d, files in os.walk(SNAP):
        for fn in sorted(files):
            print("  -", os.path.relpath(os.path.join(root, fn), SNAP).replace("\\", "/"))


if __name__ == "__main__":
    main()
