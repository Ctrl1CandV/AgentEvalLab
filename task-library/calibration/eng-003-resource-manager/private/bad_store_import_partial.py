#!/usr/bin/env python3
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_store  # noqa: E402


class ResourceStore(ref_store.ResourceStore):
    def import_data(self, payload, fmt="json", mode="merge"):
        try:
            obj = json.loads(payload)
            recs = obj["resources"] if isinstance(obj, dict) else obj
        except Exception:
            return {"ok": False, "errors": [{"field": "payload", "code": "parse_error"}]}
        added = 0
        for rec in recs:  
            if self.add(rec.get("title"), rec.get("url"), rec.get("tags"), rec.get("notes"))["ok"]:
                added += 1
        return {"ok": True, "added": added, "updated": 0, "mode": mode}


if __name__ == "__main__":
    pass
