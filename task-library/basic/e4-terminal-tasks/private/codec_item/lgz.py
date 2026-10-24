"""lgz: a line-oriented log compressor. Shipped to the model only as compiled bytecode (lgz.pyc, docstrings stripped).

Format, for the record (the model must recover it from the bytecode):
- MAGIC "LGZ\\x02", a flags byte (bit 0: the input ended with a newline), and the line count as a varint.
- Each line: a marker byte, 1 when the line opens with a timestamp YYYY-MM-DDTHH:MM:SS.mmmZ (a valid UTC date, followed by a
  space or the end of the line), then its distance in milliseconds from the previous timestamp as a zigzag varint (the
  first from 2000-01-01T00:00:00.000Z); else 0. A timestamp on a new UTC day empties the token table.
- Then the rest of the line as items, closed by 0xC0. The rest splits into maximal runs of spaces and of other bytes.
  A run of n spaces is 0xC0 | n, in chunks of at most 63. A token that is a canonical decimal integer of at most 18
  digits ("0", or an optional "-" and no leading zero) is 0x40 and its zigzag varint. Another token is its index in a
  move-to-front table (0..47) when there, else a literal: 0x80 | min(n, 63), then varint(n - 63) when n >= 63, then
  the bytes XORed with (0x5A + 13 * i + n) & 0xFF. Literals of at least three bytes enter the table at the front; the
  table keeps 48 entries.
- CRC-32 of the input, little-endian.
"""
import datetime
import re
import sys
import zlib

MAGIC = b"LGZ\x02"
CAPACITY = 48
MIN_ENTRY = 3
STAMP_LENGTH = 24
DAY_MS = 86_400_000
_STAMP = re.compile(rb"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.(\d{3})Z")
_NUMBER = re.compile(rb"0|-?[1-9][0-9]{0,17}")
_PIECE = re.compile(rb" +|[^ ]+")
_EPOCH = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)


def _varint(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _zigzag(value):
    return value * 2 if value >= 0 else -value * 2 - 1


def _stamp(line):
    match = _STAMP.match(line)
    if match is None or line[STAMP_LENGTH:STAMP_LENGTH + 1] not in (b"", b" "):
        return None
    fields = [int(group) for group in match.groups()]
    try:
        moment = datetime.datetime(*fields[:6], fields[6] * 1000, tzinfo=datetime.timezone.utc)
    except ValueError:
        return None
    return (moment - _EPOCH) // datetime.timedelta(milliseconds=1)


class _Table:
    def __init__(self):
        self.entries = []

    def lookup(self, token):
        if token in self.entries:
            index = self.entries.index(token)
            self.entries.insert(0, self.entries.pop(index))
            return index
        if len(token) >= MIN_ENTRY:
            self.entries.insert(0, token)
            del self.entries[CAPACITY:]
        return None


def _literal(token):
    size = len(token)
    head = bytes([0x80 | min(size, 63)]) + (_varint(size - 63) if size >= 63 else b"")
    return head + bytes(byte ^ ((0x5A + 13 * index + size) & 0xFF) for index, byte in enumerate(token))


def encode(data):
    trailing = data.endswith(b"\n")
    lines = data.split(b"\n")
    if trailing or not data:
        lines.pop()
    out = bytearray(MAGIC)
    out.append(1 if trailing else 0)
    out += _varint(len(lines))
    table, previous, day = _Table(), 0, None
    for line in lines:
        moment = _stamp(line)
        if moment is None:
            out.append(0)
        else:
            out.append(1)
            out += _varint(_zigzag(moment - previous))
            previous = moment
            if day is not None and moment // DAY_MS != day:
                table.entries.clear()
            day = moment // DAY_MS
            line = line[STAMP_LENGTH:]
        for piece in _PIECE.findall(line):
            if piece[0] == 0x20:
                for start in range(0, len(piece), 63):
                    out.append(0xC0 | len(piece[start:start + 63]))
            elif _NUMBER.fullmatch(piece):
                out.append(0x40)
                out += _varint(_zigzag(int(piece)))
            else:
                index = table.lookup(piece)
                out += bytes([index]) if index is not None else _literal(piece)
        out.append(0xC0)
    out += zlib.crc32(data).to_bytes(4, "little")
    return bytes(out)


def main(argv):
    if len(argv) != 2:
        print("usage: python3 lgz.pyc INPUT OUTPUT", file=sys.stderr)
        return 2
    with open(argv[0], "rb") as handle:
        data = handle.read()
    with open(argv[1], "wb") as handle:
        handle.write(encode(data))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
