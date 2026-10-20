"""Event logs for the speedup item, deterministic from a seed. Most rows are canonical; a share are quirks that the
original program treats in its own way, among them gaps of exactly 30 minutes and bursts of exactly ten seconds: timestamps in forms that strptime accepts leniently or rejects, offsets with
and without a colon, users with spaces and capitals, paths with queries and trailing slashes, empty referrers,
non-integer statuses, and rows with a single field."""
import csv
import datetime
import io
import random

PATHS = ["/", "/home", "/home/", "/api/items", "/api/items/", "/api/items?page=2", "/api/orders", "/api/orders?id=17", "/search?q=a,b",
         "/search", "/account/settings", "/account/settings/", "/static/app.js", "/login", "/logout", "/api/users", "/api/users?sort=name",
         "/help", "/help/contact", "/checkout", "/cart", "/cart/", "/api/v2/export", "/api/v2/import"]
REFERRERS = ["", "", "", "https://search.example", "https://news.example", "/home", "/cart", "/search", "/api/items", "newsletter", "ads"]
OFFSETS = ["Z"] * 6 + ["+02:00", "-05:00", "+05:30", "+00:00"]


def stamp(moment, rng, quirky):
    """moment is UTC; written in a random offset, canonical or (when quirky) in another form."""
    offset = rng.choice(OFFSETS)
    if offset == "Z":
        local, suffix = moment, "Z"
    else:
        sign = 1 if offset[0] == "+" else -1
        delta = datetime.timedelta(hours=int(offset[1:3]), minutes=int(offset[4:6])) * sign
        local, suffix = moment + delta, offset
    text = local.strftime("%Y-%m-%dT%H:%M:%S.") + f"{local.microsecond // 1000:03d}" + suffix
    if not quirky:
        return text
    kind = rng.randrange(7)
    if kind == 0:
        return local.strftime("%Y-%m-%dT%H:%M:%S") + suffix  # no fraction: strptime rejects it
    if kind == 1:
        return text[:-1] + "z" if suffix == "Z" else text.replace(suffix, suffix.replace(":", ""))  # lowercase z rejected; +0200 accepted
    if kind == 2:
        return f"{local.year}-{local.month}-{local.day}T{local.hour}:{local.minute}:{local.second}.{local.microsecond // 100000}{suffix}"  # lenient
    if kind == 3:
        return text.replace(f"-{local.month:02d}-", "-02-").replace(f"-{local.day:02d}T", "-30T")  # 30 February: rejected
    if kind == 4:
        return text.replace("T", "t", 1)  # strptime matches literals regardless of case: accepted
    if kind == 5:
        return local.strftime("%Y-%m-%dT%H:%M:%S.") + f"{local.microsecond:06d}" + suffix  # six fraction digits: accepted
    return " " + text  # leading space: rejected


def events(seed, rows, quirk_share):
    rng = random.Random(seed)
    users = [f"user{index:04d}" for index in range(max(20, rows // 80))]
    bursty = set(rng.sample(users, len(users) // 15))
    clock = {user: datetime.datetime(2026, 9, 14, 0, 0, tzinfo=datetime.timezone.utc) + datetime.timedelta(seconds=rng.randrange(0, 86_400))
             for user in users}
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["ts", "user", "path", "status", "bytes", "latency_ms", "referrer"])
    for _ in range(rows):
        user = rng.choice(users)
        if rng.random() < quirk_share * 0.3:
            # Boundaries: exactly 30 minutes (the same session) or 2.5 seconds (five requests in exactly ten seconds).
            step = rng.choice([1_800, 2.5])
        elif user in bursty and rng.random() < 0.5:
            step = rng.uniform(0.05, 3)
        elif rng.random() < 0.1:
            step = rng.uniform(1_800, 9_000)
        else:
            step = rng.uniform(5, 1_500)
        clock[user] += datetime.timedelta(seconds=step)
        quirky = rng.random() < quirk_share
        if quirky and rng.random() < 0.08:
            writer.writerow([f"garbage-{rng.randrange(10**6)}"])
            continue
        name = user if not quirky or rng.random() < 0.5 else rng.choice([f"  {user}", user.upper(), f"{user} "])
        status = rng.choices([200, 201, 204, 301, 304, 400, 404, 429, 500, 502, 503], weights=[50, 6, 4, 3, 5, 4, 6, 2, 3, 2, 2])[0]
        status_text = str(status) if not quirky or rng.random() < 0.85 else rng.choice([f"{status}.0", f" {status}", "n/a"])
        writer.writerow([stamp(clock[user], rng, quirky), name, rng.choice(PATHS), status_text, rng.randrange(0, 200_000), rng.randrange(1, 4_000),
                         rng.choice(REFERRERS)])
    return out.getvalue()
