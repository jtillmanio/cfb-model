import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL(".", import.meta.url)) },
  },
  test: {
    include: ["{app,lib,components}/**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**", ".next/**", "e2e/**", "**/.claude/**"],
    // Tests that spawn a shell need room (.claude/rules/web.md).
    testTimeout: 30_000,
  },
});
