import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// next.config.ts turns on cacheComponents and partialPrefetching, so `next dev` validates that
// every route can render an instant navigation shell. A page that calls redirect() throws
// NEXT_REDIRECT while it is validated, and dev logs 'Route "/": Could not validate `instant`
// because an error prevented the target segment from rendering' on every visit. The fix is
// `export const instant = false` on the page (as /login and /login/continue do); there is nothing
// to render a shell for.

const APP_DIR = fileURLToPath(new URL("../app/", import.meta.url));

/** Page files under `dir` (route groups and dynamic segments included). */
function pageFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return pageFiles(path);
    return entry.name === "page.tsx" ? [path] : [];
  });
}

/** Drop comments so prose that mentions redirect() or `instant` doesn't count. */
function code(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
}

export function redirectsWithoutOptOut(source: string): boolean {
  const text = code(source);
  return /\bredirect\(/.test(text) && !/export const instant = false\b/.test(text);
}

describe("pages that redirect opt out of instant validation", () => {
  it("flags a redirecting page without the opt-out", () => {
    const page = `import { redirect } from "next/navigation";\nexport default function P() { redirect("/x"); }`;
    expect(redirectsWithoutOptOut(page)).toBe(true);
    expect(redirectsWithoutOptOut(`${page}\nexport const instant = false;`)).toBe(false);
    // A comment that mentions redirect() or the opt-out changes nothing.
    expect(redirectsWithoutOptOut(`// redirect( and export const instant = false\nexport default () => null;`)).toBe(false);
    expect(redirectsWithoutOptOut(`${page}\n// export const instant = false;`)).toBe(true);
  });

  it("every page under web/app/ that calls redirect() sets `export const instant = false`", () => {
    const pages = pageFiles(APP_DIR);
    expect(pages.length).toBeGreaterThan(0);
    const offenders = pages
      .filter((file) => redirectsWithoutOptOut(readFileSync(file, "utf8")))
      .map((file) => relative(APP_DIR, file));
    expect(offenders).toEqual([]);
  });
});
