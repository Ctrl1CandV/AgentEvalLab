"""The codec item's logs, all deterministic: public samples (shipped with their lgz form), the archive the model must
restore, and the hidden files, each aimed at one feature of the format."""
import datetime
import random

EPOCH = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)


def stamp(text_or_ms):
    if isinstance(text_or_ms, str):
        return text_or_ms
    moment = EPOCH + datetime.timedelta(milliseconds=text_or_ms)
    return f"{moment.year:04d}-{moment.month:02d}-{moment.day:02d}T{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}." \
           f"{moment.microsecond // 1000:03d}Z"


def ms(text):
    moment = datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=datetime.timezone.utc)
    return (moment - EPOCH) // datetime.timedelta(milliseconds=1)


def service_log(seed, start, lines, step=(40, 4000), users=6, paths=8):
    """A plausible access log on one day: timestamps rising, recurring words, numbers."""
    rng = random.Random(seed)
    names = ["ana", "ben", "chen", "dana", "emil", "farah", "gus", "hana"][:users]
    routes = ["/api/v1/items", "/api/v1/orders", "/health", "/login", "/api/v1/items/search", "/static/app.js", "/api/v1/users", "/logout"][:paths]
    now, out = ms(start), []
    for _ in range(lines):
        now += rng.randint(*step)
        method = rng.choice(["GET", "GET", "GET", "POST", "PUT", "DELETE"])
        status = rng.choice([200, 200, 200, 201, 204, 301, 404, 500])
        out.append(f"{stamp(now)} INFO {method} {rng.choice(routes)} status={status} user={rng.choice(names)} took {rng.randint(1, 900)} ms "
                   f"bytes {rng.randint(0, 50000)}")
    return ("\n".join(out) + "\n").encode()


def samples():
    return {
        "access-small.log": service_log("sample-1", "2026-10-18T08:00:00.000Z", 12),
        "access-medium.log": service_log("sample-2", "2026-10-18T09:30:00.000Z", 40),
        "notes.log": b"deploy started for build 4411\ndeploy finished for build 4411\nrollback not needed\n",
    }


def archive():
    """Files to restore: common content plus some of every feature, so that a decoder that only handles the samples fails."""
    worker = []
    rng = random.Random("archive-worker")
    now = ms("2026-10-19T23:58:30.000Z")
    for index in range(70):
        now += rng.randint(500, 9000)
        job = f"job-{rng.randint(1, 30):03d}"
        worker.append(f"{stamp(now)} worker {job} {rng.choice(['queued', 'running', 'done', 'retry'])}  attempt {rng.randint(0, 4)}"
                      f"{'   ' if index % 9 == 0 else ''}")
    worker.append("   trailing summary:   70 jobs   ")
    audit = [f"user {name} changed setting {key} from {old} to {new}" for name, key, old, new in
             [("ana", "theme", "light", "dark"), ("ben", "limit", "-5", "0"), ("chen", "région", "Île-de-France", "Grand Est"),
              ("dana", "token", "00042", "42"), ("emil", "notes", "x" * 70, "y" * 200)]]
    return {
        "worker-2026-10-19.log": ("\n".join(worker) + "\n").encode(),
        "audit.log": ("\n".join(audit)).encode(),
        "access-2026-10-20.log": service_log("archive-access", "2026-10-20T00:00:00.000Z", 120, users=8),
    }


def hidden():
    """Hidden files by feature; each check passes when every file of its group decodes exactly."""
    rng = random.Random("hidden")
    words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"]
    eviction = [f"token{index:02d}" for index in range(60)]
    return {
        "words": {"words.log": ("\n".join(" ".join(rng.choice(words) for _ in range(rng.randint(1, 12))) for _ in range(80)) + "\n").encode()},
        "short-tokens": {"short.log": ("\n".join(" ".join(rng.choice(["a", "b", "ok", "no", "x1", "-", "=", "id", "alpha", "bravo", "charlie"])
                                                          for _ in range(15)) for _ in range(30)) + "\n").encode()},
        "numbers": {"numbers.log": b"0 -1 1 -0 007 00 10 -10\n123456789012345678 -123456789012345678 1234567890123456789 -999999999999999999\n"
                                   b"+5 5. 1e3 0x10 99 99 99\n"},
        "timestamps": {"timestamps.log": "\n".join([
            "2026-10-20T10:00:00.000Z start", "2026-10-20T09:59:59.999Z went back 1 ms", "2026-10-20T10:00:00.000Z",
            "1999-12-31T23:59:59.999Z before the epoch", "2026-10-20T10:00:00.000Z, comma after the stamp",
            "2026-02-30T10:00:00.000Z not a date", "2026-10-20T10:00:00.000", "2026-10-20T10:00:00Z short",
            "x 2026-10-20T10:00:00.000Z inside a line", "2026-10-20T10:00:01.500Z  two spaces after"]).encode() + b"\n"},
        "spaces": {"spaces.log": b"  leading\ntrailing  \nin   between\n" + b" " * 63 + b"\n" + b" " * 64 + b"x" + b" " * 130 + b"y\n\n\n   \nend\n"},
        "long-literals": {"long.log": b"\n".join(bytes([97 + size % 26]) * size + b" " + bytes([65 + size % 26]) * size
                                                 for size in (62, 63, 64, 126, 190, 191, 192, 1000)) + b"\n"},
        "eviction": {"eviction.log": ("\n".join(" ".join(eviction[start:start + 6]) for start in range(0, 60, 6)) + "\n" +
                                      " ".join(eviction[:12]) + "\n" + " ".join(eviction[48:]) + "\n" + " ".join(reversed(eviction)) + "\n").encode()},
        "multi-day": {"days.log": "\n".join([
            "2026-10-19T23:59:58.000Z status green repeated", "2026-10-19T23:59:59.000Z status green repeated",
            "2026-10-20T00:00:00.000Z status green repeated", "2026-10-20T00:00:01.000Z status green repeated",
            "status green repeated without a stamp", "2026-10-19T23:59:59.500Z status green back a day",
            "2026-10-22T12:00:00.000Z status green two days on", "status green repeated"]).encode() + b"\n"},
        "bytes": {"bytes.log": "café naïve 東京 emoji 🙂 é\nTabs\there\tand\there\nwindows line\r\nending\r\n".encode() + b"raw \xff\xfe bytes \xc3\n"},
        "edges": {"empty.log": b"", "newline.log": b"\n", "no-newline.log": b"last line has no newline", "blank-lines.log": b"\n\n\nx\n\n"},
    }
