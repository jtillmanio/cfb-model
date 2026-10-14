import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { briefTypecheck } from "../../scripts/typecheck/brief.mjs";

// verify.fast's typecheck (.claude/kit.json) prints this summary instead of the whole log.
const RUN = fileURLToPath(new URL("../../scripts/typecheck/run.mjs", import.meta.url));

const tscError = (n: number) =>
  `lib/zz-scratch.ts(${n},14): error TS2322: Type 'string' is not assignable to type 'number'.`;

const TSC_18 = [
  "$ pnpm --dir web typecheck && uv --directory python run pyright",
  "$ next typegen && tsc --noEmit",
  "Generating route types...",
  "✓ Types generated successfully",
  ...Array.from({ length: 18 }, (_, i) => tscError(i + 1)),
  "[ELIFECYCLE] Command failed with exit code 2.",
  "[ELIFECYCLE] Command failed with exit code 2.",
].join("\r\n");

const PYRIGHT_3 = String.raw`c:\repo\python\engine\src\engine\zz_scratch.py
  c:\repo\python\engine\src\engine\zz_scratch.py:2:12 - error: Type "int" is not assignable to return type "str"
    "int" is not assignable to "str" (reportReturnType)
  c:\repo\python\engine\src\engine\zz_scratch.py:5:10 - error: Type "Literal['x']" is not assignable to declared type "int"
    "Literal['x']" is not assignable to "int" (reportAssignmentType)
  c:\repo\python\engine\src\engine\zz_scratch.py:6:27 - error: Type "dict[str, str]" is not assignable to declared type "dict[str, int]"
    "Literal['b']" is not assignable to "int" (reportAssignmentType)
3 errors, 0 warnings, 0 informations`;

describe("briefTypecheck", () => {
  it("prints nothing when the typecheck passed", () => {
    expect(briefTypecheck("Generating route types...\n✓ Types generated successfully", 0)).toBe("");
  });

  it("shows the first 10 tsc errors and counts the rest", () => {
    const lines = briefTypecheck(TSC_18, 2).split("\n");
    expect(lines[0]).toBe("typecheck failed (exit 2): 18 errors, first 10 shown");
    expect(lines.slice(1, 11)).toEqual(Array.from({ length: 10 }, (_, i) => tscError(i + 1)));
    expect(lines[11]).toBe("... 8 more errors not shown");
    expect(lines).toHaveLength(12);
  });

  it("keeps pyright's detail lines and drops its file header and summary", () => {
    const lines = briefTypecheck(PYRIGHT_3, 1).split("\n");
    expect(lines[0]).toBe("typecheck failed (exit 1): 3 errors");
    expect(lines).toHaveLength(7);
    expect(lines[1]).toContain("zz_scratch.py:2:12 - error:");
    expect(lines[2]).toContain("(reportReturnType)");
    expect(lines.join("\n")).not.toContain("0 warnings");
  });

  it("caps each error's detail lines", () => {
    const output = [tscError(1), ...Array.from({ length: 7 }, (_, i) => `  detail ${i + 1}`)].join("\n");
    const lines = briefTypecheck(output, 2).split("\n");
    expect(lines).toEqual([
      "typecheck failed (exit 2): 1 error",
      tscError(1),
      "  detail 1",
      "  detail 2",
      "  detail 3",
      "  detail 4",
      "  ... 3 more lines",
    ]);
  });

  it("falls back to the last 40 lines when no error line is recognised", () => {
    const output = Array.from({ length: 100 }, (_, i) => `noise ${i + 1}`).join("\n");
    const lines = briefTypecheck(output, 1).split("\n");
    expect(lines[0]).toBe("typecheck failed (exit 1) with no recognised error lines; last 40 lines:");
    expect(lines.slice(1)).toEqual(Array.from({ length: 40 }, (_, i) => `noise ${i + 61}`));
  });

  it("says so when a failed typecheck printed nothing", () => {
    expect(briefTypecheck("\r\n", 2)).toBe("typecheck failed (exit 2) with no output");
  });
});

describe("scripts/typecheck/run.mjs", () => {
  const run = (command: string) => spawnSync(process.execPath, [RUN, command], { encoding: "utf8" });

  it("exits with the command's exit code and prints the brief", () => {
    const result = run("exit 3");
    expect(result.status).toBe(3);
    expect(result.stdout).toContain("typecheck failed (exit 3)");
  });

  it("prints nothing and exits 0 when the command passes", () => {
    const result = run("echo ok");
    expect(result.status).toBe(0);
    expect(result.stdout).toBe("");
  });
});
