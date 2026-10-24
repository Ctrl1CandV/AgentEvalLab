"""CDN edge request logs for the compress item, deterministic from a seed.

A day of traffic is simulated: clients from a pool (each with a fixed address, region, user agent, account and HTTP
version) open sessions that walk the shop's routes, edges number their requests, and the collector writes the lines
slightly out of order. The structure a compressor can use is therefore real but has to be found in the data: the edge,
user agent, account and protocol follow from the address; request ids count up per edge; images follow the product a
client just viewed; a resource's size depends only on the resource and status; the upstream follows from the route.

Normal logs have only well-formed lines. With a quirk share, damaged and unusual lines are mixed in: truncated lines,
extra fields, escaped quotes, invalid UTF-8, CRLF endings, blank lines, other timestamp forms, tabs and very long lines.
"""
import datetime
import random
import zlib

REGIONS = {
    "eu": {"edges": ["fra-01", "fra-02", "fra-03", "ams-01", "ams-02"], "prefixes": [5, 31, 46, 77, 79, 85, 88, 91, 141, 176, 185, 212]},
    "us": {"edges": ["iad-01", "iad-02", "iad-03", "sfo-01"], "prefixes": [24, 50, 66, 67, 68, 71, 73, 98, 107, 172, 174]},
    "ap": {"edges": ["sin-01", "nrt-01"], "prefixes": [1, 27, 36, 42, 49, 58, 101, 110, 114, 118]},
}
REGION_WEIGHTS = [("eu", 0.5), ("us", 0.38), ("ap", 0.12)]
BROWSERS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.{m} Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_{m} like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.{m} Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{f}.0) Gecko/20100101 Firefox/{f}.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:{f}.0) Gecko/20100101 Firefox/{f}.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36 Edg/{v}.0.0.0",
]
APPS = ["ShopApp/4.{a}.{p} (Android {o}; {d})", "ShopApp/4.{a}.{p} (iOS 18.{m}; iPhone{i},{j})"]
DEVICES = ["Pixel 8", "Pixel 7a", "SM-S911B", "SM-A546B", "M2101K6G", "CPH2449"]
BOTS = ["Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
        "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)"]
MONITOR_UA = "edge-probe/2.3"
WORDS = ["lamp", "desk", "chair", "kettle", "mug", "towel", "pillow", "blanket", "rug", "shelf", "plant", "vase", "frame", "mirror", "clock",
         "candle", "basket", "bowl", "plate", "glass", "knife", "pan", "pot", "spoon", "tray", "box", "bag", "jacket", "shirt", "shoes",
         "socks", "scarf", "hat", "gloves", "umbrella", "wallet", "watch", "headphones", "speaker", "charger", "cable", "mouse", "keyboard",
         "monitor", "laptop", "stand", "backpack", "bottle", "jar", "soap", "brush", "comb", "sofa", "table", "stool", "bench", "curtain",
         "duvet", "sheet", "lantern", "heater", "fan", "blender", "toaster", "grinder", "scale", "timer", "oak", "walnut", "linen", "wool",
         "cotton", "ceramic", "steel", "brass", "glass", "bamboo", "blue", "green", "grey", "black", "white", "red", "small", "large", "set"]
CATEGORIES = ["kitchen", "living-room", "bedroom", "bath", "office", "garden", "lighting", "textiles", "storage", "decor", "outdoor",
              "electronics", "audio", "cables", "bags", "clothing", "shoes", "accessories", "kids", "gifts", "sale", "new-in"]
SORTS = ["relevance", "price_asc", "price_desc", "newest", "rating"]
UPSTREAMS = {"home": "web", "static": "static", "product": "catalog", "image": "media", "reviews": "reviews", "search": "search",
             "category": "catalog", "cart": "cart", "cart-add": "cart", "checkout": "orders", "order": "orders", "session": "auth",
             "health": "-", "robots": "web", "sitemap": "web"}


def crc(text):
    return zlib.crc32(text.encode())


def stamp(ms):
    moment = datetime.datetime(1970, 1, 1) + datetime.timedelta(milliseconds=ms)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


def zipf(rng, n, s=1.1):
    """An index in [0, n) with Zipf-like weights, by inverse transform on a continuous approximation."""
    u = rng.random()
    value = int((u * (n ** (1 - s) - 1) + 1) ** (1 / (1 - s))) - 1
    return min(max(value, 0), n - 1)


class Client:
    def __init__(self, rng, index):
        region = rng.choices([name for name, _ in REGION_WEIGHTS], [weight for _, weight in REGION_WEIGHTS])[0]
        self.region = region
        roll = rng.random()
        self.kind = "browser" if roll < 0.62 else "app" if roll < 0.93 else "bot"
        if rng.random() < 0.09 and self.kind != "bot":
            self.ip = "2a0" + str(rng.randrange(1, 10)) + ":" + ":".join(f"{rng.randrange(0, 65536):x}" for _ in range(3)) + "::" + f"{rng.randrange(1, 65536):x}"
        else:
            self.ip = f"{rng.choice(REGIONS[region]['prefixes'])}.{rng.randrange(0, 256)}.{rng.randrange(0, 256)}.{rng.randrange(1, 255)}"
        edges = REGIONS[region]["edges"]
        self.edge = edges[crc(self.ip) % len(edges)]
        if self.kind == "browser":
            template = BROWSERS[zipf(rng, len(BROWSERS), 1.3)]
            self.ua = template.format(v=rng.choice([127, 128, 129, 129, 130, 130, 130]), m=rng.randrange(0, 7), f=rng.choice([130, 131, 131, 132]))
            self.version = "2" if rng.random() < 0.9 else "1.1"
        elif self.kind == "app":
            template = APPS[rng.randrange(2)]
            self.ua = template.format(a=rng.choice([10, 11, 12, 12, 12]), p=rng.randrange(0, 4), o=rng.choice([13, 14, 15]), d=rng.choice(DEVICES),
                                      m=rng.randrange(0, 7), i=rng.choice([14, 15, 16, 17]), j=rng.randrange(1, 4))
            self.version = "2"
        else:
            self.ua = rng.choice(BOTS)
            self.version = "1.1"
        self.uid = str(rng.randrange(100_000, 999_999)) if self.kind != "bot" and rng.random() < 0.55 else "-"
        self.seen = set()
        self.cart = 0
        self.orders = rng.randrange(7_100_000, 7_400_000)


def route_steps(rng, client):
    """One session's requests as (route, parameters) pairs, walking the shop's pages."""
    steps = []
    if client.kind == "bot":
        for _ in range(rng.randrange(3, 30)):
            roll = rng.random()
            if roll < 0.05:
                steps.append(("robots", {}))
            elif roll < 0.15:
                steps.append(("sitemap", {"n": rng.randrange(1, 9)}))
            elif roll < 0.7:
                steps.append(("product", {"pid": zipf(rng, 30_000, 1.02) + 1}))
            else:
                steps.append(("category", {"cat": rng.choice(CATEGORIES), "sort": "relevance", "page": rng.randrange(1, 12)}))
        return steps
    if client.kind == "browser":
        steps.append(("home", {}))
        for asset in ("app", "vendor", "runtime", "css"):
            steps.append(("static", {"asset": asset}))
    pid = None
    for _ in range(max(1, int(rng.expovariate(1 / 8)))):
        roll = rng.random()
        if pid is not None and roll < 0.35:
            pid = max(1, pid + rng.randrange(-25, 26)) if rng.random() < 0.5 else zipf(rng, 30_000) + 1
            steps.append(("product", {"pid": pid}))
        elif pid is not None and roll < 0.5:
            steps.append(("reviews", {"pid": pid, "page": 1}))
            if rng.random() < 0.3:
                steps.append(("reviews", {"pid": pid, "page": 2}))
        elif pid is not None and roll < 0.62:
            steps.append(("cart-add", {}))
            steps.append(("cart", {}))
            if rng.random() < 0.35:
                if client.uid == "-" and rng.random() < 0.5:
                    steps.append(("checkout", {}))
                    steps.append(("session", {}))
                steps.append(("checkout", {}))
                steps.append(("order", {}))
        elif roll < 0.82:
            words = [WORDS[zipf(rng, len(WORDS))] for _ in range(1 if rng.random() < 0.7 else 2)]
            steps.append(("search", {"q": "+".join(words), "page": 1}))
            if rng.random() < 0.25:
                steps.append(("search", {"q": "+".join(words), "page": 2}))
            pid = zipf(rng, 30_000) + 1
            steps.append(("product", {"pid": pid}))
        else:
            steps.append(("category", {"cat": CATEGORIES[zipf(rng, len(CATEGORIES))], "sort": rng.choice(SORTS), "page": 1}))
            pid = zipf(rng, 30_000) + 1
            steps.append(("product", {"pid": pid}))
        if steps[-1][0] == "product" and client.kind == "browser":
            for size in (160, 480, 960)[: rng.randrange(1, 4)]:
                steps.append(("image", {"pid": steps[-1][1]["pid"], "size": size}))
    return steps


def request(route, params, client, rng, deploy):
    """(method, path, status, bytes, cache) for one request; sizes depend only on the resource and status."""
    method, cache, status = "GET", "MISS", 200
    if route == "home":
        path, size, cache = "/", 18_412, "HIT"
    elif route == "static":
        names = {"app": f"/static/js/app.{deploy}.js", "vendor": "/static/js/vendor.7b21d0aa.js", "runtime": "/static/js/runtime.0c4e9f13.js",
                 "css": "/static/css/main.5d0b77e1.css"}
        sizes = {"app": 412_377 + crc(deploy) % 9000, "vendor": 1_204_118, "runtime": 4_212, "css": 88_903}
        path, size, cache = names[params["asset"]], sizes[params["asset"]], "HIT"
    elif route == "product":
        path = f"/api/v2/products/{params['pid']}"
        size, cache = 1_200 + (params["pid"] * 2_654_435_761) % 2_900, "HIT" if rng.random() < 0.7 else "MISS"
        if params["pid"] % 101 == 0:
            status, size = 404, 162
    elif route == "image":
        path = f"/img/p/{params['pid']}/{params['size']}.webp"
        size, cache = params["size"] * 40 + (params["pid"] * 40_503 + params["size"]) % (params["size"] * 30), "HIT" if rng.random() < 0.95 else "MISS"
    elif route == "reviews":
        path = f"/api/v2/products/{params['pid']}/reviews?page={params['page']}"
        size = 400 + (params["pid"] * 7 + params["page"] * 1_013) % 6_000
    elif route == "search":
        path = f"/api/v2/search?q={params['q']}&page={params['page']}"
        size = 600 + crc(params["q"] + str(params["page"])) % 8_000
    elif route == "category":
        path = f"/api/v2/categories/{params['cat']}/products?sort={params['sort']}&page={params['page']}"
        size, cache = 900 + crc(path) % 12_000, "HIT" if rng.random() < 0.5 else "MISS"
    elif route == "cart":
        path, size, cache = "/api/v2/cart", 310 + 87 * client.cart, "-"
    elif route == "cart-add":
        client.cart += 1
        method, path, status, size, cache = "POST", "/api/v2/cart/items", 201, 64, "-"
    elif route == "checkout":
        method, path, cache = "POST", "/api/v2/checkout", "-"
        if client.uid == "-":
            status, size = 401, 98
        elif rng.random() < 0.04:
            status, size = 402, 131
        else:
            status, size = 200, 412
            client.cart = 0
    elif route == "order":
        client.orders += rng.randrange(1, 40)
        path, size, cache = f"/api/v2/orders/{client.orders}", 1_544 + client.orders % 700, "-"
    elif route == "session":
        method, path, size, cache = "POST", "/api/v2/session", 233, "-"
        client.uid = str(rng.randrange(100_000, 999_999))
    elif route == "robots":
        path, size, cache = "/robots.txt", 412, "HIT"
    elif route == "sitemap":
        path, size, cache = f"/sitemap-{params['n']}.xml", 48_000 + params["n"] * 3_117, "HIT"
    else:
        path, size, cache = "/healthz", 2, "-"
    if method == "GET" and route in ("static", "image") and path in client.seen and rng.random() < 0.85:
        status, size = 304, 0
    if method == "GET":
        client.seen.add(path)
    if status == 200 and client.kind == "bot" and rng.random() < 0.02:
        status, size, cache = 429, 54, "-"
    elif status in (200, 201) and rng.random() < 0.003:
        status, size, cache = 500, 214, "-"
    return method, path, status, size, cache


BASE_LATENCY = {"home": 9, "static": 1.2, "product": 14, "image": 2.5, "reviews": 31, "search": 48, "category": 26, "cart": 12,
                "cart-add": 22, "checkout": 180, "order": 35, "session": 64, "robots": 1, "sitemap": 6, "health": 0.4}


def events(seed, lines, quirk_share=0.0):
    """The log as bytes: `lines` well-formed lines, with damaged or unusual lines mixed in at quirk_share."""
    rng = random.Random(seed)
    day = datetime.datetime(2026, 9, 1) + datetime.timedelta(days=rng.randrange(0, 60))
    start = int((day - datetime.datetime(1970, 1, 1)).total_seconds() * 1000) + rng.randrange(0, 12) * 3_600_000
    clients = [Client(rng, index) for index in range(max(50, lines // 6))]
    monitors = [(f"10.{rng.randrange(0, 255)}.{rng.randrange(0, 255)}.{rng.randrange(1, 255)}", edge)
                for region in REGIONS.values() for edge in region["edges"]]
    counters = {edge: rng.randrange(0, 2 ** 31) for region in REGIONS.values() for edge in region["edges"]}
    deploy_old, deploy_new = f"{rng.getrandbits(32):08x}", f"{rng.getrandbits(32):08x}"
    # Sessions start as a Poisson process; their requests follow at exponential gaps.
    requests = []
    session_rate = lines / 9.5 / 3_600_000  # sessions per millisecond for about an hour of traffic
    clock = start
    duration_guess = int(lines / 9.5 / session_rate)
    deploy_at = start + duration_guess // 2
    while len(requests) < lines:
        clock += int(rng.expovariate(session_rate)) + 1
        # Regulars come back often; most sessions are from occasional visitors.
        client = clients[zipf(rng, len(clients), 0.9)] if rng.random() < 0.4 else rng.choice(clients)
        moment = clock
        for route, params in route_steps(rng, client):
            requests.append((moment, client, route, params))
            moment += int(rng.expovariate(1 / (900 if route in ("static", "image") else 3_500))) + 1
    end = max(moment for moment, *_ in requests[:lines])
    for ip, edge in monitors:
        moment = start + rng.randrange(0, 10_000)
        while moment < end:
            requests.append((moment, (ip, edge), "health", {}))
            moment += 10_000 + rng.randrange(-40, 41)
    requests.sort(key=lambda entry: entry[0])
    records = []
    for moment, client, route, params in requests:
        if route == "health":
            ip, edge = client
            method, path, status, size, cache, ua, uid, version = "GET", "/healthz", 200, 2, "-", MONITOR_UA, "-", "1.1"
        else:
            deploy = deploy_new if moment >= deploy_at else deploy_old
            method, path, status, size, cache = request(route, params, client, rng, deploy)
            ip, edge, ua, uid, version = client.ip, client.edge, client.ua, client.uid, client.version
        counters[edge] += 1
        if rng.random() < 0.004:
            continue  # a line lost on the way to the collector
        latency = 0.4 if route == "health" else BASE_LATENCY[route] * rng.lognormvariate(0, 0.45) * (0.3 if cache == "HIT" else 1)
        line = (f'{stamp(moment)} {edge} {counters[edge]:08x} {ip} {uid} "{method} {path} HTTP/{version}" {status} {size} '
                f'{latency:.1f} {cache} {UPSTREAMS[route]} "{ua}"')
        # The collector receives lines a little out of order.
        records.append((moment + rng.randrange(0, 60), line))
    records.sort(key=lambda entry: entry[0])
    out = [line.encode() for _, line in records[:lines]]
    if quirk_share:
        out = [quirk(rng, line) if rng.random() < quirk_share else line for line in out]
    return b"\n".join(out) + b"\n"


def quirk(rng, line):
    """A damaged or unusual version of a well-formed line."""
    kind = rng.randrange(12)
    if kind == 0:
        return line[: rng.randrange(1, len(line))]  # truncated
    if kind == 1:
        return line + b" x-debug=" + str(rng.randrange(1, 9)).encode()  # an extra field
    if kind == 2:
        return line[:-1] + b' (compatible; \\"Quoted\\" build)"'  # escaped quotes in the user agent
    if kind == 3:
        return line.replace(b" HTTP/", b"?ref=caf\xe9 HTTP/", 1)  # Latin-1 byte: invalid UTF-8
    if kind == 4:
        return line + b"\r"  # CRLF ending
    if kind == 5:
        return b""  # blank line
    if kind == 6:
        return line[:19] + line[23:]  # timestamp without milliseconds
    if kind == 7:
        return line[:23] + b"+00:00" + line[24:]  # another offset form
    if kind == 8:
        return line.replace(b" ", b"\t", 2)  # tabs between the first fields
    if kind == 9:
        return line.replace(b" HTTP/", b"&utm=" + b"x" * rng.randrange(2_000, 9_000) + b" HTTP/", 1)  # a very long line
    if kind == 10:
        return line.replace(b'" 200 ', b'" - ', 1)  # a status the edge could not record
    return "  ".join(line.decode("latin-1").split(" ", 3)).encode("latin-1")  # doubled spaces


# The sample has a few damaged lines so that they are visible; the hidden days a and b have none, and the quirks log is
# almost a third damaged.
SAMPLE = ("compress-sample", 15_000, 0.003)
HIDDEN = {"day-a": ("compress-hidden-a", 50_000, 0.0), "day-b": ("compress-hidden-b", 30_000, 0.0), "quirks": ("compress-hidden-quirks", 8_000, 0.3)}
