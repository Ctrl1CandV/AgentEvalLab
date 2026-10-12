import { appendFile, mkdir, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { resolve, join } from "node:path";

import { defaultBudget, validateBudget } from "./config.js";
import { guardEventSink } from "./events.js";
import { createPiRunner } from "./harness/pi.js";
import { persistedExecution } from "./privacy.js";
import type { Budget, ModelSelection, RunInput, Runner } from "./types.js";

export interface RunOptions<Input extends RunInput> {
  input: Input;
  model: ModelSelection;
  budget?: Budget;
  outputRoot: string;
  runner?: Runner<Input>;
}

/** Record one model call without a dataset, answer key, or score. */
export async function runHarness<Input extends RunInput>(options: RunOptions<Input>) {
  const budget = { ...(options.budget ?? defaultBudget) };
  validateBudget(budget);

  // ---- Output directory: runs/<uuid>/ ----
  const id = randomUUID();
  const directory = resolve(options.outputRoot, id);
  await mkdir(directory, { recursive: true });

  // Append events to events.jsonl in sequence; a promise chain preserves emission order.
  let sequence = 0;
  let pending = Promise.resolve();
  const events = guardEventSink((type, counts, details) => {
    const entry = { sequence: ++sequence, at: new Date().toISOString(), type, counts, ...(details ? { details } : {}) };
    pending = pending.then(() =>
      appendFile(join(directory, "events.jsonl"), JSON.stringify(entry) + "\n"),
    );
    return pending;
  });

  await writeFile(
    join(directory, "config.json"),
    JSON.stringify({ id, model: options.model, budget }, null, 2),
  );
  await events.emit("run_started");

  // ---- Execute and persist ----
  const runner = options.runner ?? createPiRunner<Input>({ trialId: id });
  try {
    const execution = await runner(options.input, options.model, budget, events.emit);

    await pending; // Wait for the final events to be persisted.
    events.check(); // Do not write an incomplete success record if event persistence failed.

    const saved = persistedExecution(execution, budget.maxOutputChars);
    await writeFile(join(directory, "execution.json"), JSON.stringify(saved, null, 2));
    await events.emit("run_completed", {
      modelCalls: execution.modelCalls,
      toolCalls: execution.toolCalls,
    });
    return { directory, execution: saved };
  } catch (error) {
    await pending;
    events.check();
    await events.emit("run_failed");
    throw error;
  }
}
