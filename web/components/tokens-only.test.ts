import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// Hard rule 7: components use the design tokens only. A colour literal or an arbitrary Tailwind
// value in web/components/ is a one-off style that bypasses the system.

const COMPONENTS_DIR = fileURLToPath(new URL(".", import.meta.url));

const BANNED: { name: string; pattern: RegExp }[] = [
  { name: "hex colour", pattern: /#[0-9a-fA-F]{3,8}\b/ },
  { name: "rgb( literal", pattern: /\brgba?\(/ },
  { name: "oklch( literal", pattern: /\boklch\(/ },
  { name: "arbitrary colour [#…]", pattern: /\[#/ },
  // `[13px]`, `ring-[3px]`, `w-[1.5rem]`, `top-[calc(…)]`, `h-[100vh]`
  {
    name: "arbitrary size [13px]",
    pattern: /\[-?\d*\.?\d+(px|rem|em|vh|vw|%|ch|fr)?\]|\[calc\(/,
  },
];

/** Drop comments so `#125` or `[13px]` in prose does not trip the scan. */
export function stripComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
}

export function findViolations(source: string): string[] {
  const code = stripComments(source);
  return BANNED.filter(({ pattern }) => pattern.test(code)).map(({ name }) => name);
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    // The scan skips test files: they hold the banned samples on purpose.
    return /\.(ts|tsx|css)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : [];
  });
}

describe("tokens only (AC-4)", () => {
  it("flags each banned form in a sample", () => {
    expect(findViolations('<i className="bg-[#b699eb]" />')).toContain("arbitrary colour [#…]");
    expect(findViolations("const c = '#b699eb';")).toContain("hex colour");
    expect(findViolations("color: rgb(10 20 30);")).toContain("rgb( literal");
    expect(findViolations("color: rgba(10, 20, 30, 0.5);")).toContain("rgb( literal");
    expect(findViolations("color: oklch(0.7 0.1 300);")).toContain("oklch( literal");
    expect(findViolations('<i className="text-[13px]" />')).toContain("arbitrary size [13px]");
    expect(findViolations('<i className="ring-[3px]" />')).toContain("arbitrary size [13px]");
    expect(findViolations('<i className="w-[1.5rem]" />')).toContain("arbitrary size [13px]");
    expect(findViolations('<i className="h-[calc(100%-2px)]" />')).toContain(
      "arbitrary size [13px]",
    );
  });

  it("passes theme utilities, variants and comments", () => {
    expect(findViolations('<i className="bg-edge size-5 [&_svg]:size-3 text-label" />')).toEqual(
      [],
    );
    expect(findViolations("// the pill (PR #125, `[13px]` in the board)\nconst a = 1;")).toEqual(
      [],
    );
    expect(findViolations("/* #b699eb is --edge */ const a = 1;")).toEqual([]);
    expect(findViolations('const url = "https://example.com";')).toEqual([]);
  });

  it("no file under web/components/ has one", () => {
    const files = sourceFiles(COMPONENTS_DIR);
    expect(files.length).toBeGreaterThan(0);
    const violations = files.flatMap((file) =>
      findViolations(readFileSync(file, "utf8")).map(
        (name) => `${relative(COMPONENTS_DIR, file)}: ${name}`,
      ),
    );
    expect(violations).toEqual([]);
  });
});
