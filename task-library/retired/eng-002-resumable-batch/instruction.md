# Task: Resumable Batch Processor (eng-002)

Build a command-line tool from an empty directory. It walks an input directory, applies a deterministic transform to each file, writes results to an output directory, and maintains a journal for safe resume. All acceptance-relevant interfaces and semantics below are fixed; internal design is yours.

## Runtime

- Python 3.13, standard library only (including os, hashlib, json, argparse). No third-party dependencies or network access.
- Deliver a standalone script, for example batch.py.

## Command line

    python <script> --input-dir D --output-dir O --journal J

## Deterministic transform

For each input file, read its bytes and produce an output at O/<relative-path>.json, mirroring the directory structure. Use / in relative paths.

The output bytes are UTF-8 JSON followed by one newline. Serialize this object with json.dumps(obj, sort_keys=True, ensure_ascii=False):

    {
      "rel_path": "<relative path>",
      "input_sha256": "<SHA-256 of input bytes>",
      "bytes": <integer byte length>,
      "lines": <text.count("\\n")>,
      "words": <len(text.split())>
    }

Here text is input_bytes.decode("utf-8", errors="replace").

## Traversal

- Recursively process ordinary files under D, sorted by relative path in ascending order.
- Do not follow symbolic links.
- Ignore temporary files in the output directory whose suffix is .part.

## Journal protocol

- J is a JSON Lines file with one object per line:
  {"rel_path": "<relative path>", "input_sha256": "<hex>", "output_sha256": "<hex>", "status": "done"}
- Ignore lines that cannot be parsed, especially a truncated final line left by a crash.
- When appending, if J exists but does not end with a newline, append a newline first so the new entry cannot be joined to a damaged fragment.

## Resume contract

Skip an item if and only if all of these conditions hold:
1. The journal contains a valid status=done entry for the item.
2. Its input_sha256 equals the current input file's SHA-256.
3. The output file exists.
4. The output file's SHA-256 equals the journal's output_sha256.

Otherwise, process the item again. Do not rely on the journal alone or on the input hash alone.

## Publish and recovery

- Atomic publish: write to <final-name>.part, then use os.replace to move it to the final name. Append the done journal entry only after replace succeeds.
- Recovery window: if a crash occurs after output replace but before journal append, there is no done entry, so resume safely recomputes the deterministic output. This is at-least-once behavior; exactly-once is not promised.
- A .part file is never a published output. After a successful run, the output directory must contain no .part files.

## Guarantees and non-guarantees

- Guaranteed: after a single-process interruption (exception or termination), the next run converges to a correct final state. Every input has a correct output, and the journal has a done entry whose output hash matches each actual output.
- Not guaranteed: power-loss durability (no fsync and no exactly-once promise) or multi-process concurrency. The tool is designed for one process.

## Output and exit codes

- Emit one JSON line to stdout per item:
  {"action": "processed|skipped|error", "rel_path": "..."}; errors include an error field.
- End with:
  {"summary": {"processed": <int>, "skipped": <int>, "errors": <int>, "total": <int>}}
- Exit codes: 0 on success, 1 if any item fails, 2 for usage errors such as a missing input directory.

## Deliverables

1. A runnable script meeting this contract.
2. README.md documenting usage, journal format, resume and recovery semantics, guarantees and non-guarantees, and assumptions about unspecified details.

## Public materials

- public/example_input/: a small sample input tree.
- public/example_expected/: its expected output for debugging.

## Out of scope

Signal-handler details for real process kills, distributed execution, concurrency, performance, and network access are out of scope. Internal implementation is unrestricted.
