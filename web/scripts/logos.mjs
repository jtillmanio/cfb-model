// Writes the team logos the chip shows as static files (D-173, amends D-154): one 40px PNG per
// team id in web/public/logos/<id>.png, served by Vercel's CDN with no function behind it, and
// web/lib/logo-ids.json, the ids that have a file (the chip draws the colour dot for any other).
//
//   pnpm --dir web logos --staged       every id in the staged teams (data/staging/teams.parquet)
//   pnpm --dir web logos <ids-file>     ids one per line (`-`: stdin)
//   --refresh                           render ids that already have a file again
//
// Each id is CFBD's team id, the <id> in `teams.logo_url`
// (https://cdn.collegefootballdata.com/logos/500/<id>.png). --staged reads them from the staged
// teams with DuckDB through uv: zero CFBD API calls (README › Team logos). This downloads CFBD's 500px PNG from its
// CDN (not the API, so outside the call budget) and renders it at LOGO_PX with next/og's
// ImageResponse, as the old /logos route did on every cold request. An id whose PNG CFBD doesn't
// have is listed and skipped. Logos change about once a season: run it again then, with --refresh.
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

// next/og has no exports map, so plain Node needs the file name.
import { ImageResponse } from "next/og.js";
import { createElement } from "react";

const WEB = fileURLToPath(new URL("..", import.meta.url));
export const LOGO_DIR = join(WEB, "public/logos");
export const IDS_PATH = join(WEB, "lib/logo-ids.json");
/** The chip's 20px slot at 2x; web/lib/logos.ts' LOGO_PX. */
const LOGO_PX = 40;
const ID = /^\d{1,6}$/;
const LOGO_FILE = /^(\d{1,6})\.png$/;

/** Prints the staged teams' logo ids, one per line (python/ has DuckDB; web/ doesn't). */
const STAGED_IDS = String.raw`
import duckdb
rows = duckdb.sql(r"""
  select regexp_extract(logo_url, '^https://cdn\.collegefootballdata\.com/logos/500/(\d+)\.png$', 1) as id
  from '../data/staging/teams.parquet'
""").fetchall()
print("\n".join(sorted({r[0] for r in rows if r[0]}, key=int)))
`;

/** The staged teams' ids, read through uv from python/. */
function stagedIds() {
  const run = spawnSync("uv", ["--directory", join(WEB, "../python"), "run", "python", "-c", STAGED_IDS], {
    encoding: "utf8",
    maxBuffer: 16 * 1024 * 1024,
  });
  if (run.status !== 0) {
    console.error(`logos: reading data/staging/teams.parquet failed: ${(run.stderr || run.error?.message || "").trim()}`);
    process.exit(1);
  }
  return run.stdout;
}

/** @param {string} id */
const cfbdLogoUrl = (id) => `https://cdn.collegefootballdata.com/logos/500/${id}.png`;

/** The ids with a file in public/logos, as numbers, ascending. */
export function logoIds(dir = LOGO_DIR) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .map((name) => LOGO_FILE.exec(name)?.[1])
    .filter((id) => id !== undefined)
    .map(Number)
    .sort((a, b) => a - b);
}

/**
 * CFBD's PNG for a team, rendered at LOGO_PX; null when CFBD has none.
 * @param {string} id
 * @returns {Promise<Uint8Array | null>}
 */
async function render(id) {
  const upstream = await fetch(cfbdLogoUrl(id), { signal: AbortSignal.timeout(20_000) }).catch(() => null);
  if (!upstream?.ok || upstream.headers.get("content-type")?.split(";")[0] !== "image/png") return null;
  const src = `data:image/png;base64,${Buffer.from(await upstream.arrayBuffer()).toString("base64")}`;
  const img = createElement("img", { src, alt: "", width: LOGO_PX, height: LOGO_PX, style: { objectFit: "contain" } });
  const image = new ImageResponse(img, { width: LOGO_PX, height: LOGO_PX });
  return new Uint8Array(await image.arrayBuffer());
}

async function main() {
  const args = process.argv.slice(2);
  const refresh = args.includes("--refresh");
  const file = args.find((a) => !a.startsWith("--"));
  if (!file && !args.includes("--staged")) {
    console.error("usage: pnpm --dir web logos --staged | <ids-file> | - [--refresh]");
    process.exit(1);
  }
  const text = file ? readFileSync(file === "-" ? 0 : file, "utf8") : stagedIds();
  const ids = [...new Set(text.split(/\s+/).filter(Boolean))];
  const bad = ids.filter((id) => !ID.test(id));
  if (bad.length) {
    console.error(`logos: not team ids: ${bad.slice(0, 5).join(", ")}`);
    process.exit(1);
  }
  mkdirSync(LOGO_DIR, { recursive: true });
  const todo = ids.filter((id) => refresh || !existsSync(join(LOGO_DIR, `${id}.png`)));
  /** @type {string[]} */
  const missing = [];
  let next = 0;
  // A few at a time: CFBD's CDN is someone else's.
  await Promise.all(
    Array.from({ length: 6 }, async () => {
      while (next < todo.length) {
        const id = todo[next++];
        const png = await render(id);
        if (png) writeFileSync(join(LOGO_DIR, `${id}.png`), png);
        else missing.push(id);
      }
    }),
  );
  writeFileSync(IDS_PATH, `${JSON.stringify(logoIds())}\n`);
  console.log(
    `logos: ${todo.length - missing.length} rendered, ${ids.length - todo.length} already there, ` +
      `${logoIds().length} in ${IDS_PATH}`,
  );
  if (missing.length) console.log(`logos: CFBD has no PNG for ${missing.sort().join(", ")}`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) await main();
