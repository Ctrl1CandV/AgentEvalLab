# Candidate Task Card: eng-002 Resumable Batch Processor

## Identity

- ID: `eng-002-resumable-batch`
- Family: `eng-resumable-state`
- Status: screening; development use; not frozen
- Primary capability: stateful batch processing
- Secondary evidence: atomicity, recovery reasoning, and file-state handling
- Source: original task design; fixtures are synthetic.

## User goal

Build a CLI that processes every file in an input directory, writes deterministic outputs, and records enough state to resume safely after an interruption.

## Fixed contract

- Use input and output directories plus a persistent journal.
- Identify completed inputs by content hash, and skip an item only when its recorded output still exists and its hash is valid.
- Write each output to a temporary path and atomically publish it before appending a completed journal record.
- Reprocess missing, changed, or incomplete items. A full second run must be idempotent.
- Declare journal format and failure policy in the README.
- The package distinguishes static recovery fixtures, injected process interruption, and true operating-system kill behavior.

## Evidence and limits

The calibrated package contains fixtures for partial journals, stale temporary files, changed input, and damaged final records. Its offline calibration is limited to the recorded single-process recovery contract; it does not claim power-loss exactly-once guarantees.
