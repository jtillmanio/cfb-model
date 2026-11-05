import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// D-157: the shell is drawn on the server only. A client module that imports it (an error.tsx,
// say) ships the whole shell to the browser on every page load (TASK-054's Lighthouse run).
describe("shell stays server-side", () => {
  const WEB = fileURLToPath(new URL("../../", import.meta.url));
  const SHELL = /from\s+["']@\/components\/shell\/(app-shell|sidebar|top-bar|mobile-tabs)["']|from\s+["']\.\/(app-shell|sidebar|top-bar|mobile-tabs)["']/;

  function clientModules(dir: string): string[] {
    return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) return clientModules(path);
      if (!/\.tsx?$/.test(entry.name) || /\.test\.tsx?$/.test(entry.name)) return [];
      return /^\s*["']use client["']/.test(readFileSync(path, "utf8")) ? [path] : [];
    });
  }

  it("flags a client module that imports the shell", () => {
    expect(SHELL.test('import { AppShell } from "@/components/shell/app-shell";')).toBe(true);
    expect(SHELL.test('import { NAV_ICONS } from "./sidebar";')).toBe(true);
    expect(SHELL.test('import { ApiUnreachable } from "@/components/shell/api-unreachable";')).toBe(
      false,
    );
  });

  it("no client module under app/ or components/ imports it", () => {
    const files = [...clientModules(join(WEB, "app")), ...clientModules(join(WEB, "components"))];
    expect(files.length).toBeGreaterThan(0);
    const offenders = files
      .filter((file) => SHELL.test(readFileSync(file, "utf8")))
      .map((file) => relative(WEB, file));
    expect(offenders).toEqual([]);
  });
});
