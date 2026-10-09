import { join } from "node:path";

import type { NextConfig } from "next";

// Locally, the one env file is the repo root's .env.local (.env.example), which Next doesn't read
// from web/. Load it here; variables already set (Playwright's test values, the shell) still win.
if (!process.env.VERCEL) {
  try {
    process.loadEnvFile(join(process.cwd(), "..", ".env.local"));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
  }
}

// On Vercel, /api/py/* is routed to the FastAPI service by vercel.json before it reaches Next.
// Locally (dev, e2e) Next forwards it to the API itself, so both run on one origin.
const localApi = process.env.VERCEL ? undefined : (process.env.API_URL ?? "http://127.0.0.1:8000");

const nextConfig: NextConfig = {
  agentRules: false,
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return localApi ? [{ source: "/api/py/:path*", destination: `${localApi}/api/py/:path*` }] : [];
  },
};

export default nextConfig;
