import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import LOGO_IDS from "./logo-ids.json";
import { logoPath, LOGO_PX } from "./logos";

// Team logos are static files in web/public/logos, served by Vercel's CDN with no function behind
// them (D-173, amending D-154's route), and never from CFBD's CDN (D-101).
const WEB = fileURLToPath(new URL("..", import.meta.url));
const LOGO_DIR = join(WEB, "public/logos");
const files = existsSync(LOGO_DIR) ? readdirSync(LOGO_DIR) : [];

/** Width and height from a PNG's IHDR chunk. */
function pngSize(bytes: Buffer) {
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

describe("logoPath", () => {
  it("maps CFBD's logo URL to the app's own static file", () => {
    expect(logoPath("https://cdn.collegefootballdata.com/logos/500/194.png")).toBe("/logos/194.png");
    expect(logoPath("https://cdn.collegefootballdata.com/logos/500/2005.png")).toBe("/logos/2005.png");
  });

  it("returns null for no logo, another host, or another path, so the chip draws the dot", () => {
    expect(logoPath(null)).toBeNull();
    expect(logoPath("")).toBeNull();
    expect(logoPath("https://a.espncdn.com/i/teamlogos/ncaa/500/194.png")).toBeNull();
    expect(logoPath("http://cdn.collegefootballdata.com/logos/500/194.png")).toBeNull();
    expect(logoPath("https://cdn.collegefootballdata.com/logos-dark/500/194.png")).toBeNull();
    expect(logoPath("https://cdn.collegefootballdata.com/logos/500/../x.png")).toBeNull();
  });

  it("returns null for a team with no file, so a missing logo is a dot, never a 404 rendered by a function", () => {
    expect(LOGO_IDS).not.toContain(999999);
    expect(logoPath("https://cdn.collegefootballdata.com/logos/500/999999.png")).toBeNull();
  });
});

describe("web/public/logos (D-173)", () => {
  it("holds one file per id in logo-ids.json, and nothing else", () => {
    expect(LOGO_IDS.length).toBeGreaterThan(600);
    expect(files.sort()).toEqual(LOGO_IDS.map((id) => `${id}.png`).sort());
    expect(LOGO_IDS).toEqual([...LOGO_IDS].sort((a, b) => a - b));
  });

  it("holds 40px PNGs, a few KB each: the 20px slot at 2x", () => {
    expect(LOGO_PX).toBe(40);
    for (const name of files) {
      const bytes = readFileSync(join(LOGO_DIR, name));
      expect(bytes.subarray(1, 4).toString("latin1"), name).toBe("PNG");
      expect(pngSize(bytes), name).toEqual({ width: LOGO_PX, height: LOGO_PX });
      expect(bytes.byteLength, name).toBeLessThan(8_000);
    }
  });

  it("has no route under app/logos: a function resizing images per request is what this replaced", () => {
    expect(existsSync(join(WEB, "app/logos"))).toBe(false);
  });
});

describe("static files skip the sign-in proxy (proxy.ts)", () => {
  // The matcher, read from the source: importing proxy.ts would load Auth.js.
  const source = readFileSync(join(WEB, "proxy.ts"), "utf8");
  const literal = /matcher: \[("(?:[^"\\]|\\.)*")\]/.exec(source)?.[1] ?? '""';
  const runsProxy = (path: string) => new RegExp(`^${JSON.parse(literal) as string}$`).test(path);

  it("never runs the proxy for a logo, the favicon or robots.txt, so none is redirected to /login", () => {
    for (const path of ["/logos/194.png", "/favicon.ico", "/robots.txt"]) expect(runsProxy(path), path).toBe(false);
  });

  it("still runs it for a page", () => {
    for (const path of ["/", "/teams", "/design-system"]) expect(runsProxy(path), path).toBe(true);
  });
});
