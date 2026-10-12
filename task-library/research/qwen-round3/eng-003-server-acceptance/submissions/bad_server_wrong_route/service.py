#!/usr/bin/env python3
import csv
import io
import json
import os
import re
import time

URL_RE = re.compile(r"^https?://\S+$")
MAX_TITLE, MAX_NOTES, MAX_TAGS, MAX_TAG_LEN = 200, 5000, 20, 50


class StoreError(Exception):
    pass


class ResourceStore:
    def __init__(self, path, clock=None):
        self.path = path
        self._clock = clock or time.time
        self._data = {"next_id": 1, "resources": []}
        self.recovered_from_corrupt = False
        self.load()

    
    def load(self):
        if not os.path.isfile(self.path):
            self._data = {"next_id": 1, "resources": []}
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
            if not isinstance(d, dict) or not isinstance(d.get("resources"), list):
                raise ValueError("bad store shape")
            self._data = {"next_id": int(d.get("next_id", 1)), "resources": d["resources"]}
        except (json.JSONDecodeError, ValueError, OSError):
            try:
                os.replace(self.path, self.path + ".corrupt")  
            except OSError:
                pass
            self._data = {"next_id": 1, "resources": []}
            self.recovered_from_corrupt = True

    def _save(self):
        d = os.path.dirname(os.path.abspath(self.path)) or "."
        os.makedirs(d, exist_ok=True)
        tmp = self.path + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, sort_keys=True)
        os.replace(tmp, self.path)  

    
    def _by_id(self, rid):
        for r in self._data["resources"]:
            if r["id"] == str(rid):
                return r
        return None

    def _clean_tags(self, tags):
        out = []
        for tg in (tags or []):
            if isinstance(tg, str):
                s = tg.strip()
                if s and s not in out:
                    out.append(s)
        return out

    def _validate(self, title, url, tags, notes, partial=False):
        errs = []
        if (not partial) or title is not None:
            t = (title or "").strip()
            if not t:
                errs.append({"field": "title", "code": "required"})
            elif len(t) > MAX_TITLE:
                errs.append({"field": "title", "code": "too_long", "value": str(len(t))})
        if (not partial) or url is not None:
            u = (url or "").strip()
            if not u:
                errs.append({"field": "url", "code": "required"})
            elif not URL_RE.match(u):
                errs.append({"field": "url", "code": "invalid_format", "value": u})
        if tags is not None:
            if not isinstance(tags, list) or any(not isinstance(x, str) for x in tags):
                errs.append({"field": "tags", "code": "invalid_type"})
            else:
                cleaned = self._clean_tags(tags)
                if len(cleaned) > MAX_TAGS:
                    errs.append({"field": "tags", "code": "too_many"})
                if any(len(x) > MAX_TAG_LEN for x in cleaned):
                    errs.append({"field": "tags", "code": "tag_too_long"})
        if notes is not None:
            if not isinstance(notes, str):
                errs.append({"field": "notes", "code": "invalid_type"})
            elif len(notes) > MAX_NOTES:
                errs.append({"field": "notes", "code": "too_long"})
        return errs

    
    def add(self, title, url, tags=None, notes=None):
        errs = self._validate(title, url, tags, notes)
        if errs:
            return {"ok": False, "errors": errs}
        now = self._clock()
        rid = str(self._data["next_id"])
        self._data["next_id"] += 1
        res = {"id": rid, "title": title.strip(), "url": url.strip(),
               "tags": self._clean_tags(tags), "notes": (notes or "").strip(),
               "created_at": now, "updated_at": now}
        self._data["resources"].append(res)
        self._save()
        return {"ok": True, "resource": dict(res)}

    def edit(self, rid, title=None, url=None, tags=None, notes=None):
        r = self._by_id(rid)
        if not r:
            return {"ok": False, "errors": [{"field": "id", "code": "not_found", "value": str(rid)}]}
        errs = self._validate(title, url, tags, notes, partial=True)
        if errs:
            return {"ok": False, "errors": errs}
        if title is not None:
            r["title"] = title.strip()
        if url is not None:
            r["url"] = url.strip()
        if tags is not None:
            r["tags"] = self._clean_tags(tags)
        if notes is not None:
            r["notes"] = notes.strip()
        r["updated_at"] = self._clock()
        self._save()
        return {"ok": True, "resource": dict(r)}

    def delete(self, rid):
        if not self._by_id(rid):
            return {"ok": False, "errors": [{"field": "id", "code": "not_found", "value": str(rid)}]}
        self._data["resources"] = [x for x in self._data["resources"] if x["id"] != str(rid)]
        self._save()
        return {"ok": True, "id": str(rid)}

    def get(self, rid):
        r = self._by_id(rid)
        return {"ok": True, "resource": dict(r)} if r else {"ok": False, "errors": [{"field": "id", "code": "not_found"}]}

    def list(self, tag=None, text=None):
        rs = sorted(self._data["resources"], key=lambda r: int(r["id"]))
        if tag:
            rs = [r for r in rs if tag.strip() in r["tags"]]
        if text:
            t = text.strip().lower()
            rs = [r for r in rs if t in r["title"].lower() or t in r["notes"].lower() or t in r["url"].lower()]
        return [dict(r) for r in rs]

    
    def export(self, fmt="json"):
        rs = sorted(self._data["resources"], key=lambda r: int(r["id"]))
        if fmt == "json":
            return json.dumps({"resources": [dict(r) for r in rs]}, ensure_ascii=False, sort_keys=True, indent=2)
        if fmt == "csv":
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            w.writerow(["id", "title", "url", "tags", "notes", "created_at", "updated_at"])
            for r in rs:
                w.writerow([r["id"], r["title"], r["url"], ";".join(r["tags"]), r["notes"], r["created_at"], r["updated_at"]])
            return buf.getvalue()
        raise StoreError("bad format")

    def import_data(self, payload, fmt="json", mode="merge"):
        try:
            if fmt == "json":
                obj = json.loads(payload)
                recs = obj["resources"] if isinstance(obj, dict) else obj
                if not isinstance(recs, list):
                    raise ValueError("resources list required")
            elif fmt == "csv":
                recs = []
                for row in csv.DictReader(io.StringIO(payload)):
                    tg = row.get("tags", "") or ""
                    recs.append({"id": row.get("id") or None, "title": row.get("title"),
                                 "url": row.get("url"), "tags": [x for x in tg.split(";") if x],
                                 "notes": row.get("notes", "")})
            else:
                raise StoreError("bad format")
        except (json.JSONDecodeError, ValueError, KeyError, csv.Error) as e:
            return {"ok": False, "errors": [{"field": "payload", "code": "parse_error", "value": str(e)[:80]}]}
        
        allerrs, seen, norm = [], set(), []
        for i, rec in enumerate(recs):
            if not isinstance(rec, dict):
                allerrs.append({"record": i, "field": "_", "code": "invalid_type"})
                continue
            rid = rec.get("id")
            errs = self._validate(rec.get("title"), rec.get("url"), rec.get("tags"), rec.get("notes"))
            allerrs += [dict(e, record=i) for e in errs]
            if rid is not None:
                rid = str(rid)
                if rid in seen:
                    allerrs.append({"record": i, "field": "id", "code": "duplicate_in_payload", "value": rid})
                seen.add(rid)
            norm.append((rid, {"title": (rec.get("title") or "").strip(), "url": (rec.get("url") or "").strip(),
                               "tags": self._clean_tags(rec.get("tags")), "notes": (rec.get("notes") or "").strip()}))
        if allerrs:
            return {"ok": False, "errors": allerrs}
        if mode == "replace":
            self._data["resources"] = []
        added = updated = 0
        for rid, vals in norm:
            now = self._clock()
            if rid is not None and self._by_id(rid):
                self._by_id(rid).update(vals)
                self._by_id(rid)["updated_at"] = now
                updated += 1
                continue
            if rid is None:
                rid = str(self._data["next_id"])
                self._data["next_id"] += 1
            else:
                try:
                    if int(rid) >= self._data["next_id"]:
                        self._data["next_id"] = int(rid) + 1
                except ValueError:
                    pass
            self._data["resources"].append({"id": str(rid), **vals, "created_at": now, "updated_at": now})
            added += 1
        self._save()
        return {"ok": True, "added": added, "updated": updated, "mode": mode}
