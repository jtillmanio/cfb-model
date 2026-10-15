import js from "@eslint/js";
import { defineConfig, globalIgnores } from "eslint/config";
import globals from "globals";

// Lints the repo's Node scripts. web/ has its own config (Next.js rules) and `pnpm lint` runs it
// separately, so everything it owns is ignored here.
export default defineConfig([
  globalIgnores([
    "web/**",
    "python/**",
    "**/node_modules/**",
    "design/**",
    "data/**",
    "docs/**",
    ".claude/**",
  ]),
  {
    files: ["scripts/**/*.mjs"],
    extends: [js.configs.recommended],
    languageOptions: { globals: globals.node },
  },
]);
