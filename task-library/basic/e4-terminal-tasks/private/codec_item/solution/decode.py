#!/usr/bin/env python3
"""Reference decoder for lgz files: python3 decode.py INPUT OUTPUT, or decode(data) -> bytes."""
import datetime
import sys
import zlib

EPOCH = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
DAY_MS = 86_400_000


class Reader:
    def __init__(self, data):
        self.data, self.position = data, 0

    def byte(self):
        value = self.data[self.position]
        self.position += 1
        return value

    def take(self, size):
        chunk = self.data[self.position:self.position + size]
        if len(chunk) != size:
            raise ValueError("truncated")
        self.position += size
        return chunk

    def varint(self):
        value = shift = 0
        while True:
            byte = self.byte()
            value |= (byte & 0x7F) << shift
            shift += 7
            if not byte & 0x80:
                return value


def unzigzag(value):
    return value // 2 if value % 2 == 0 else -(value + 1) // 2


def stamp_text(milliseconds):
    moment = EPOCH + datetime.timedelta(milliseconds=milliseconds)
    return f"{moment.year:04d}-{moment.month:02d}-{moment.day:02d}T{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}." \
           f"{moment.microsecond // 1000:03d}Z".encode()


def decode(data):
    reader = Reader(data)
    if reader.take(4) != b"LGZ\x02":
        raise ValueError("not an lgz file")
    trailing = reader.byte() & 1
    count = reader.varint()
    table, previous, day, lines = [], 0, None, []
    for _ in range(count):
        line = bytearray()
        if reader.byte() == 1:
            moment = previous + unzigzag(reader.varint())
            previous = moment
            if day is not None and moment // DAY_MS != day:
                table.clear()
            day = moment // DAY_MS
            line += stamp_text(moment)
        while True:
            tag = reader.byte()
            if tag == 0xC0:
                break
            if tag >= 0xC0:
                line += b" " * (tag & 0x3F)
            elif tag >= 0x80:
                size = tag & 0x3F
                if size == 63:
                    size += reader.varint()
                token = bytes(byte ^ ((0x5A + 13 * index + size) & 0xFF) for index, byte in enumerate(reader.take(size)))
                if len(token) >= 3:
                    table.insert(0, token)
                    del table[48:]
                line += token
            elif tag >= 0x40:
                line += str(unzigzag(reader.varint())).encode()
            else:
                token = table.pop(tag)
                table.insert(0, token)
                line += token
        lines.append(bytes(line))
    out = b"\n".join(lines) + (b"\n" if trailing else b"")
    if int.from_bytes(reader.take(4), "little") != zlib.crc32(out):
        raise ValueError("checksum mismatch")
    return out


def main(argv):
    with open(argv[0], "rb") as handle:
        data = handle.read()
    with open(argv[1], "wb") as handle:
        handle.write(decode(data))


if __name__ == "__main__":
    main(sys.argv[1:])
