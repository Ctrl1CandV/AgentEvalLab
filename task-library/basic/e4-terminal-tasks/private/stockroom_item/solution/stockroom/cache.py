"""A small file cache for slow queries. Entries expire after an hour."""
import json
import os
import time

TTL_SECONDS = 3600


def get(directory, key):
    try:
        with open(os.path.join(directory, key + ".json"), encoding="utf-8") as handle:
            entry = json.load(handle)
    except FileNotFoundError:
        return None
    if time.time() - entry["at"] > TTL_SECONDS:
        return None
    return entry["value"]


def put(directory, key, value):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, key + ".json"), "w", encoding="utf-8") as handle:
        json.dump({"at": time.time(), "value": value}, handle)


def invalidate(directory, key):
    try:
        os.remove(os.path.join(directory, key + ".json"))
    except FileNotFoundError:
        pass
