#!/usr/bin/env python3
"""The compress item's upper anchor: a compressor written for the edge-log format.

Each well-formed line is split into fields, and each field goes to its own stream after a transform that uses the
log's structure: timestamps as deltas; addresses through a recency cache and a table; the edge, account, protocol and
user agent as "same as this address last time"; request ids as deltas per edge; paths as a shape plus numbers, a number
coded as "same as this address's last request at that position" when it is; sizes and upstreams as "same as the last
time this resource or route was seen". Every stream is then compressed with LZMA. A line that does not come back byte
for byte from its parsed fields is stored raw, so any input round-trips.

Usage: python3 reference.py compress IN OUT | decompress IN OUT
"""
import lzma
import re
import sys

LINE = re.compile(rb'(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)\.(\d{3})Z (\S+) ([0-9a-f]{8}) (\S+) (\S+) "([A-Z]+) (\S+) HTTP/(1\.1|2)" '
                  rb'(\d{3}) (0|[1-9]\d*) (0|[1-9]\d*)\.(\d) (\S+) (\S+) "([^"\\]*)"')
NUMBER = re.compile(rb"(?<=[/=])(?:0|[1-9]\d*)(?=[/?&.]|$)")
STREAMS = ["kind", "raw", "ts", "ip", "ipindex", "ipnew", "profile", "edge", "uid", "ua", "rid", "method", "shape", "shapenew", "number",
           "status", "size", "rt", "cache", "upstream"]
FILTERS = [{"id": lzma.FILTER_LZMA2, "preset": 9 | lzma.PRESET_EXTREME}]
CACHE = 64
TEMPLATE = b'%04d-%02d-%02dT%02d:%02d:%02d.%03dZ %s %08x %s %s "%s %s HTTP/%s" %s %d %d.%d %s %s "%s"'


def varint(out, value):
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)


def zigzag(value):
    return value * 2 if value >= 0 else -value * 2 - 1


def unzigzag(value):
    return value >> 1 if value % 2 == 0 else -((value + 1) >> 1)


class Reader:
    def __init__(self, data):
        self.data, self.position = data, 0

    def varint(self):
        value, shift = 0, 0
        while True:
            byte = self.data[self.position]
            self.position += 1
            value |= (byte & 0x7F) << shift
            if byte < 0x80:
                return value
            shift += 7

    def byte(self):
        self.position += 1
        return self.data[self.position - 1]

    def take(self, count):
        self.position += count
        return self.data[self.position - count:self.position]

    def text(self):
        return self.take(self.varint())


def days_from_civil(year, month, day):
    year -= month <= 2
    era = year // 400
    yoe = year - era * 400
    doy = (153 * (month + (-3 if month > 2 else 9)) + 2) // 5 + day - 1
    return era * 146_097 + yoe * 365 + yoe // 4 - yoe // 100 + doy - 719_468


def civil_from_days(days):
    days += 719_468
    era = days // 146_097
    doe = days - era * 146_097
    yoe = (doe - doe // 1_460 + doe // 36_524 - doe // 146_096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    month = mp + (3 if mp < 10 else -9)
    return yoe + era * 400 + (month <= 2), month, doy - (153 * mp + 2) // 5 + 1


def clock(ms):
    days, rest = divmod(ms, 86_400_000)
    hours, rest = divmod(rest, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    return (*civil_from_days(days), hours, minutes, *divmod(rest, 1000))


def compress(data):
    streams = {name: bytearray() for name in STREAMS}
    parts = data.split(b"\n")
    varint(streams["kind"], len(parts))
    previous_ts = 0
    recent, ip_index = [], {}
    profiles, last_numbers, last_rid = {}, {}, {}
    shapes, sizes, upstreams, edges, uas = {}, {}, {}, {}, {}
    for line in parts:
        match = LINE.fullmatch(line)
        if match is not None:
            (year, month, day, hours, minutes, seconds, millis, edge, rid, ip, uid, method, path, version, status, size, whole, tenth,
             cache, upstream, ua) = match.groups()
            ms = ((days_from_civil(int(year), int(month), int(day)) * 24 + int(hours)) * 60 + int(minutes)) * 60_000 + int(seconds) * 1000 + int(millis)
            rid_value, size_value, tenths = int(rid, 16), int(size), int(whole) * 10 + int(tenth)
            # Only lines that come back exactly from their fields are coded by field.
            if b"\x00" in path or TEMPLATE % (*clock(ms), edge, rid_value, ip, uid, method, path, version, status, size_value, tenths // 10,
                                              tenths % 10, cache, upstream, ua) != line:
                match = None
        if match is None:
            streams["kind"].append(1)
            varint(streams["raw"], len(line))
            streams["raw"] += line
            continue
        streams["kind"].append(0)
        varint(streams["ts"], zigzag(ms - previous_ts))
        previous_ts = ms
        # The address: its rank in a small recency cache, or 0 and its table index (a new one at the end of the table).
        if ip in recent:
            rank = recent.index(ip)
            del recent[rank]
            varint(streams["ip"], rank + 1)
        else:
            streams["ip"].append(0)
            index = ip_index.get(ip)
            if index is None:
                index = ip_index[ip] = len(ip_index)
                varint(streams["ipnew"], len(ip))
                streams["ipnew"] += ip
            varint(streams["ipindex"], index)
            if len(recent) >= CACHE:
                recent.pop()
        recent.insert(0, ip)
        profile = (edge, uid, version, ua)
        if profiles.get(ip) == profile:
            streams["profile"].append(0)
        else:
            streams["profile"].append(1 if version == b"2" else 2)
            for value, table, stream in ((edge, edges, "edge"), (ua, uas, "ua")):
                if value in table:
                    varint(streams[stream], table[value] + 1)
                else:
                    table[value] = len(table)
                    streams[stream].append(0)
                    varint(streams[stream], len(value))
                    streams[stream] += value
            varint(streams["uid"], len(uid))
            streams["uid"] += uid
            profiles[ip] = profile
        varint(streams["rid"], zigzag(rid_value - last_rid.get(edge, 0)))
        last_rid[edge] = rid_value
        if method == b"GET":
            streams["method"].append(0)
        elif method == b"POST":
            streams["method"].append(1)
        else:
            streams["method"].append(2)
            varint(streams["method"], len(method))
            streams["method"] += method
        numbers = [int(number) for number in NUMBER.findall(path)]
        shape = NUMBER.sub(b"\x00", path)
        if shape in shapes:
            varint(streams["shape"], shapes[shape] + 1)
        else:
            shapes[shape] = len(shapes)
            streams["shape"].append(0)
            varint(streams["shapenew"], len(shape))
            streams["shapenew"] += shape
        previous_numbers = last_numbers.get(ip, ())
        for position, value in enumerate(numbers):
            if position < len(previous_numbers) and previous_numbers[position] == value:
                streams["number"].append(0)
            else:
                varint(streams["number"], value + 1)
        last_numbers[ip] = numbers
        streams["status"] += status
        key = (method, path, status)
        if sizes.get(key) == size_value:
            streams["size"].append(0)
        else:
            varint(streams["size"], size_value + 1)
            sizes[key] = size_value
        varint(streams["rt"], tenths)
        streams["cache"] += cache + b"\n"
        if upstreams.get(shape) == upstream:
            streams["upstream"] += b"\n"
        else:
            streams["upstream"] += upstream + b"\n"
            upstreams[shape] = upstream
    out = bytearray(b"PLG1")
    blocks = [lzma.compress(bytes(streams[name]), format=lzma.FORMAT_RAW, filters=FILTERS) if streams[name] else b"" for name in STREAMS]
    for block in blocks:
        varint(out, len(block))
    for block in blocks:
        out += block
    return bytes(out)


def decompress(blob):
    if blob[:4] != b"PLG1":
        raise ValueError("not a packlog file")
    header = Reader(blob)
    header.position = 4
    lengths = [header.varint() for _ in STREAMS]
    position = header.position
    data = {}
    for name, length in zip(STREAMS, lengths):
        block = blob[position:position + length]
        position += length
        data[name] = lzma.decompress(block, format=lzma.FORMAT_RAW, filters=FILTERS) if block else b""
    streams = {name: Reader(value) for name, value in data.items()}
    caches = iter(data["cache"].split(b"\n"))
    upstream_codes = iter(data["upstream"].split(b"\n"))
    kind = streams["kind"]
    lines = []
    previous_ts = 0
    recent, ip_table = [], []
    profiles, last_numbers, last_rid = {}, {}, {}
    shapes, sizes, upstreams, edges, uas = [], {}, {}, [], []
    for _ in range(kind.varint()):
        if kind.byte() == 1:
            lines.append(streams["raw"].text())
            continue
        ms = previous_ts + unzigzag(streams["ts"].varint())
        previous_ts = ms
        rank = streams["ip"].varint()
        if rank:
            ip = recent.pop(rank - 1)
        else:
            index = streams["ipindex"].varint()
            if index == len(ip_table):
                ip_table.append(streams["ipnew"].text())
            ip = ip_table[index]
            if len(recent) >= CACHE:
                recent.pop()
        recent.insert(0, ip)
        flag = streams["profile"].byte()
        if flag == 0:
            edge, uid, version, ua = profiles[ip]
        else:
            values = []
            for table, stream in ((edges, "edge"), (uas, "ua")):
                code = streams[stream].varint()
                if code:
                    values.append(table[code - 1])
                else:
                    table.append(streams[stream].text())
                    values.append(table[-1])
            edge, ua = values
            uid = streams["uid"].text()
            version = b"2" if flag == 1 else b"1.1"
            profiles[ip] = (edge, uid, version, ua)
        rid_value = last_rid.get(edge, 0) + unzigzag(streams["rid"].varint())
        last_rid[edge] = rid_value
        code = streams["method"].byte()
        method = b"GET" if code == 0 else b"POST" if code == 1 else streams["method"].text()
        code = streams["shape"].varint()
        if code:
            shape = shapes[code - 1]
        else:
            shape = streams["shapenew"].text()
            shapes.append(shape)
        previous_numbers = last_numbers.get(ip, ())
        pieces = shape.split(b"\x00")
        numbers = []
        for position in range(len(pieces) - 1):
            value = streams["number"].varint()
            numbers.append(previous_numbers[position] if value == 0 else value - 1)
        last_numbers[ip] = numbers
        path = pieces[0] + b"".join(str(number).encode() + piece for number, piece in zip(numbers, pieces[1:]))
        status = streams["status"].take(3)
        key = (method, path, status)
        value = streams["size"].varint()
        if value == 0:
            size_value = sizes[key]
        else:
            size_value = value - 1
            sizes[key] = size_value
        tenths = streams["rt"].varint()
        cache = next(caches)
        upstream = next(upstream_codes)
        if upstream:
            upstreams[shape] = upstream
        else:
            upstream = upstreams[shape]
        lines.append(TEMPLATE % (*clock(ms), edge, rid_value, ip, uid, method, path, version, status, size_value, tenths // 10, tenths % 10,
                                 cache, upstream, ua))
    return b"\n".join(lines)


def main():
    mode, source, target = sys.argv[1:4]
    with open(source, "rb") as handle:
        data = handle.read()
    result = compress(data) if mode == "compress" else decompress(data)
    with open(target, "wb") as handle:
        handle.write(result)


if __name__ == "__main__":
    main()
