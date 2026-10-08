import type { NextConfig } from "next";

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
