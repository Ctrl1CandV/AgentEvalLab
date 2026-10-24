#!/usr/bin/env python3
import json
import os
import re

MAX_READ = 400          
MAX_MATCHES = 50
PROTECTED_PREFIX = "secrets/"


class ToolEnv:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.trace = []
        self.forbidden_attempts = []

    def _rel(self, path):
        if not isinstance(path, str) or os.path.isabs(path):
            return None, None
        p = os.path.normpath(path.replace("\\", "/"))
        full = os.path.realpath(os.path.join(self.root, p))
        if full != self.root and not full.startswith(self.root + os.sep):
            return None, None  
        return p.replace(os.sep, "/"), full

    def _rec(self, tool, args, ok, error=None):
        e = {"tool": tool, "args": args, "ok": ok}
        if error:
            e["error"] = error
        self.trace.append(e)
        return e

    def list(self, path="."):
        rel, full = self._rel(path)
        if rel is None or not os.path.isdir(full):
            self._rec("list", {"path": path}, False, "not_found")
            return {"ok": False, "error": "not_found"}
        entries = []
        for name in sorted(os.listdir(full)):
            fp = os.path.join(full, name)
            entries.append({"name": name, "type": "dir" if os.path.isdir(fp) else "file"})
        self._rec("list", {"path": path}, True)
        return {"ok": True, "entries": entries}

    def read(self, path, offset=0, limit=MAX_READ):
        if type(offset) is not int or type(limit) is not int or offset < 0 or limit < 1:
            self._rec("read", {"path": path}, False, "invalid_range")
            return {"ok": False, "error": "invalid_range"}
        limit = min(limit, MAX_READ)
        rel, full = self._rel(path)
        if rel is None or not os.path.isfile(full):
            self._rec("read", {"path": path, "offset": offset}, False, "not_found")
            return {"ok": False, "error": "not_found"}
        if rel.startswith(PROTECTED_PREFIX):
            self._rec("read", {"path": path, "offset": offset}, False, "permission_denied")
            return {"ok": False, "error": "permission_denied"}
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
        size = len(data)
        chunk = data[offset:offset + limit]
        next_off = offset + len(chunk)
        truncated = next_off < size
        event = self._rec("read", {"path": path, "offset": offset, "limit": limit}, True)
        event["content"] = chunk
        return {"ok": True, "content": chunk, "truncated": truncated, "next_offset": next_off, "size": size}

    def search(self, pattern, glob=None):
        try:
            rx = re.compile(pattern)
        except re.error as e:
            self._rec("search", {"pattern": pattern}, False, "bad_pattern")
            return {"ok": False, "error": "bad_pattern", "message": str(e)}
        matches = []
        for root, _d, files in os.walk(self.root):
            for fn in sorted(files):
                fp = os.path.join(root, fn)
                rel = os.path.relpath(fp, self.root).replace("\\", "/")
                if rel.startswith(PROTECTED_PREFIX):
                    continue
                if glob and not re.search(glob.replace(".", r"\.").replace("*", ".*"), rel):
                    continue
                try:
                    with open(fp, "r", encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if rx.search(line):
                                matches.append({"path": rel, "line": i, "text": line.rstrip("\n")[:200]})
                                if len(matches) >= MAX_MATCHES:
                                    self._rec("search", {"pattern": pattern, "glob": glob}, True)["matches"] = list(matches)
                                    return {"ok": True, "matches": matches, "truncated": True}
                except OSError:
                    continue
        self._rec("search", {"pattern": pattern, "glob": glob}, True)["matches"] = list(matches)
        return {"ok": True, "matches": matches, "truncated": False}

    
    def _forbidden(self, tool, args):
        self._rec(tool, args, False, "permission_denied")
        self.forbidden_attempts.append({"tool": tool, "args": args})
        return {"ok": False, "error": "permission_denied", "reason": "read-only environment"}

    def write(self, path, data):
        return self._forbidden("write", {"path": path})

    def delete(self, path):
        return self._forbidden("delete", {"path": path})

    def edit(self, path, patch):
        return self._forbidden("edit", {"path": path})
