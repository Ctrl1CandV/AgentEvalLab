# License and Source Audit: qwen-round3

## Method

For each task package, check whether third-party source code or prose was actually copied. Record source URL, license, version, access date, and use. This round did not recheck external licenses online; it relies on earlier notes dated 2026-09-30. No third-party downloads were made in this round.

## Copying result

The fixtures, snapshots, task copy, reference implementations, negative implementations, and acceptance scripts in this research set were authored or generated for this project. The listed sources were used for concepts, technical facts, or formats; their code or prose was not copied.

| Source | Recorded license | Use |
| --- | --- | --- |
| csvkit | MIT | CSV validation requirements prior art |
| rclone | MIT | Checkpoint and resume concepts |
| Python 3.13 standard-library documentation | PSF License v2; examples may use 0BSD | Fixed API facts |
| Google OR-Tools | Apache-2.0; documentation CC BY 4.0 | Constraint-solving concepts |
| OpenStax University Physics, Volume 1 | CC BY 4.0; some volumes include additional restrictions on LLM ingestion | Topic and difficulty reference only; no text was copied |
| WCAG 2.2 | W3C Software Notice and License | Factual accessibility thresholds |
| axe-core | MPL-2.0 | Proposed evaluator-side accessibility tool; not downloaded or bundled |
| SWE-bench, tau-bench, Design2Code, Harbor | See package metadata; some terms remain unconfirmed | Task-format inspiration only |

## Separate tool and data licenses

Tool licenses and dataset licenses are tracked separately. Any future third-party font, image, or document snapshot requires clear permission and a source record with a full SHA-256. Do not copy material where terms are unclear.

## Items not rechecked

External license pages were not revisited online during this round. Exact licenses and access terms for any source used in a future concrete task must be verified before copying or adaptation.

## Integrity

The local manifest.sha256.json covers this research directory, excluding caches, logs, and itself. It is a research artifact and does not update the main task metadata.
