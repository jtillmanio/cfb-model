import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// `pnpm lint` runs the repo-root ESLint over scripts/**/*.mjs (eslint.config.mjs). The root's
// ESLint binary is run directly so the test doesn't depend on pnpm being on PATH. ESLint 10 looks
// for the config nearest the file, so `--config` pins the root one (a web/ file would otherwise
// pick up web's own config).
const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const ESLINT = fileURLToPath(new URL("../../node_modules/eslint/bin/eslint.js", import.meta.url));

type Result = { messages: { ruleId: string | null; severity: number; message: string }[] };

function lint(path: string, source: string) {
  const run = spawnSync(
    process.execPath,
    [ESLINT, "--config", "eslint.config.mjs", "--stdin", "--stdin-filename", path, "--format", "json"],
    { cwd: ROOT, input: source, encoding: "utf8" },
  );
  const results = JSON.parse(run.stdout) as Result[];
  return { status: run.status, messages: results.flatMap((r) => r.messages) };
}

describe("root ESLint over scripts/", () => {
  it("fails an unused variable and an undefined name in scripts/perf", () => {
    const { status, messages } = lint(
      "scripts/perf/x.mjs",
      "const unused = 1;\nundefinedName();\n",
    );
    expect(status).toBe(1);
    const rules = messages.map((m) => m.ruleId);
    expect(rules).toContain("no-unused-vars");
    expect(rules).toContain("no-undef");
  }, 30_000);

  it("passes a clean source that uses Node globals", () => {
    const { status, messages } = lint("scripts/perf/x.mjs", "console.log(process.env.X);\n");
    expect(status).toBe(0);
    expect(messages).toEqual([]);
  }, 30_000);

  it("ignores web/ (web's own ESLint lints it)", () => {
    const { messages } = lint("web/x.mjs", "const unused = 1;\n");
    expect(messages.filter((m) => m.severity === 2)).toEqual([]);
    expect(messages.some((m) => /ignore/i.test(m.message))).toBe(true);
  }, 30_000);
});
