// One-command suite runs (PLAN-006 Part A): freeze HEAD into a worktree, generate one plan per family, preflight,
// smoke every family with the null agent, launch everything, retry infrastructure failures once, and write one report
// to runs/suites/<id>/report.md. Run it in the background; it exits when the report is written.
//
// Usage:
//   npm run suite -- --suite suites/dev.json --models deepseek:deepseek-flash,aliplan:qwen3.8-flash [--families E4,T1]
//                    [--reps 1] [--dry-run]
//   npm run suite -- --resume runs/suites/<id>
// --dry-run stops after the smoke step (no tokens spent); --resume continues a dry run or an interrupted suite.
import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";
import { processExecutor } from "../src/suite/executor.js";
import { SuiteRunner } from "../src/suite/run.js";

const { values } = parseArgs({ options: {
  suite: { type: "string" }, models: { type: "string" }, families: { type: "string" }, reps: { type: "string" },
  "dry-run": { type: "boolean" }, resume: { type: "string" }, help: { type: "boolean" },
} });
if (values.help || (!values.suite && !values.resume)) {
  console.log("npm run suite -- --suite suites/<name>.json --models provider:id[?thinking=level],... [--families A,B] [--reps 1] [--dry-run]\n" +
    "npm run suite -- --resume runs/suites/<id>");
  process.exit(values.help ? 0 : 2);
}
if (values.resume && (values.suite || values.models || values.families || values.reps)) throw new Error("RESUME_TAKES_NO_OTHER_ARGUMENTS");
const repoRoot = fileURLToPath(new URL("../", import.meta.url));
const runner = new SuiteRunner({
  repoRoot,
  ...(values.suite ? { suitePath: values.suite } : {}),
  ...(values.models ? { models: values.models.split(",").map(model => model.trim()).filter(Boolean) } : {}),
  ...(values.families ? { families: values.families.split(",").map(family => family.trim()).filter(Boolean) } : {}),
  ...(values.reps ? { repetitions: Number(values.reps) } : {}),
  ...(values["dry-run"] ? { dryRun: true } : {}),
  ...(values.resume ? { resume: values.resume } : {}),
}, processExecutor(repoRoot));
const result = await runner.run();
console.log(JSON.stringify({ directory: result.directory, status: result.status === 0 ? "completed" : "failed",
  flags: result.report?.flags.map(flag => `${flag.kind}${flag.family ? ` ${flag.family}` : ""}: ${flag.detail}`) ?? [] }, null, 2));
process.exitCode = result.status;
