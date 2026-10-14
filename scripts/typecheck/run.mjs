// verify.fast's typecheck (.claude/kit.json): runs `pnpm typecheck` from the repo root and exits
// with its exit code, but prints only briefTypecheck's summary, so one broken edit doesn't put the
// whole log in Claude's context. Run `pnpm typecheck` itself for the full log.
// Usage: node scripts/typecheck/run.mjs [command]   (the command defaults to `pnpm typecheck`)
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { briefTypecheck } from "./brief.mjs";

const command = process.argv.slice(2).join(" ") || "pnpm typecheck";
const run = spawnSync(`${command} 2>&1`, {
  shell: true,
  cwd: fileURLToPath(new URL("../..", import.meta.url)),
  encoding: "utf8",
  maxBuffer: 64 * 1024 * 1024,
});

if (run.error) {
  console.log(`typecheck could not start: ${run.error.message}`);
  process.exit(1);
}
const code = run.status ?? 1;
const brief = briefTypecheck(run.stdout ?? "", code);
if (brief) console.log(brief);
process.exit(code);
