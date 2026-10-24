import { createHash } from "node:crypto";
import { existsSync, linkSync, copyFileSync, mkdirSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";

// External package assets (PLAN-007 WP3.2): large repository and runtime archives that a manifest hashes as trusted
// files under assets/ but that are kept out of Git. Builders store them in a content-addressed cache
// (~/.cache/agenteval/assets/<sha256>, or AGENTEVAL_ASSET_CACHE); this script restores each declared asset into its
// package by hard link (or copy), verifying its hash. Run before checks and runs; the suite runs it in its frozen worktree.
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const cache = process.env.AGENTEVAL_ASSET_CACHE ?? join(homedir(), ".cache", "agenteval", "assets");
const sha256 = path => createHash("sha256").update(readFileSync(path)).digest("hex");

let restored = 0, present = 0;
const missing = [];
for (const tier of readdirSync(join(repoRoot, "task-library"), { withFileTypes: true })) {
  if (!tier.isDirectory() || tier.name.startsWith(".")) continue;
  for (const entry of readdirSync(join(repoRoot, "task-library", tier.name), { withFileTypes: true })) {
    const packageRoot = join(repoRoot, "task-library", tier.name, entry.name);
    const manifestPath = join(packageRoot, "manifest.json");
    if (!entry.isDirectory() || !existsSync(manifestPath)) continue;
    const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
    for (const file of manifest.files?.trusted ?? []) {
      if (!file.path.startsWith("assets/")) continue;
      const target = join(packageRoot, ...file.path.split("/"));
      if (existsSync(target)) {
        if (sha256(target) !== file.sha256) throw new Error(`ASSET_HASH_MISMATCH:${tier.name}/${entry.name}/${file.path}`);
        present++;
        continue;
      }
      const source = join(cache, file.sha256);
      if (!existsSync(source)) { missing.push(`${tier.name}/${entry.name}/${file.path} (${file.sha256})`); continue; }
      mkdirSync(dirname(target), { recursive: true });
      try { linkSync(source, target); } catch { copyFileSync(source, target); }
      if (sha256(target) !== file.sha256) throw new Error(`ASSET_HASH_MISMATCH:${tier.name}/${entry.name}/${file.path}`);
      restored++;
    }
  }
}
if (missing.length) {
  console.error(`Missing from the asset cache ${cache}; rebuild them with the package's builder:\n  ${missing.join("\n  ")}`);
  process.exit(1);
}
console.log(`Assets ready: ${present} present, ${restored} restored${statSync(cache, { throwIfNoEntry: false }) ? "" : " (no asset cache)"}.`);
