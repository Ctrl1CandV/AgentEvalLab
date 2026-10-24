## Task: compress the edge logs

Everything for this task is in the directory `public/` of the workspace. All paths below are relative to it, and the deliverables go there too; run your commands from inside it.

The platform keeps the request logs of its CDN edges for a year. `edge-sample.log.gz` is a sample of about 15,000 lines (decompress it with `gunzip -k`). The archive job compresses each log with `packlog.py`, which only calls gzip.

Rewrite `packlog.py` so that it compresses these logs as small as you can:

- `python3 packlog.py compress IN OUT` writes the compressed file OUT, and `python3 packlog.py decompress IN OUT` restores the original from it. Decompression gets nothing but the compressed file: no file written while compressing, in the workspace or elsewhere, is available to it. Files you deliver alongside `packlog.py` in `public/` are available to both.
- It must restore **any** input byte for byte, not only well-formed logs. Logs come from several edge versions and are sometimes damaged: lines that do not follow the format, invalid UTF-8, CRLF endings, blank lines, an empty file, a last line without a newline.
- Use only the Python standard library (`zlib`, `bz2` and `lzma` included), in one process with one thread.
- Each compress and each decompress run must finish within 60 seconds on one CPU core for a log of 50,000 lines.

Hidden checks run your `packlog.py` on other logs from the same edges and services, one run at a time on one core:

- `roundtrip`: two normal logs of 50,000 and 30,000 lines come back byte for byte, within the time limit.
- `roundtrip-quirks`: a damaged log, an empty file, a log whose last line has no newline, and random bytes come back byte for byte.
- `ratio-50`, `ratio-80`, `ratio-90`, `ratio-97`: the total compressed size of the two normal logs is placed on a scale from Python's `lzma` at its strongest setting (`lzma.compress(data, preset=9 | lzma.PRESET_EXTREME)`, 0%) to our own compressor written for this log format (100%). It must reach 50%, 80%, 90% and 97% of the way. These need `roundtrip`.
- The round-trip checks count only once `ratio-50` passes, so gzip or `lzma` alone earns nothing.
