import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LOGO_PX } from "@/lib/logos";

import { GET } from "./route";

// Outside Next, "use cache" is a plain string; record the lifetime each call asks for.
const { cacheLife } = vi.hoisted(() => ({ cacheLife: vi.fn() }));
vi.mock("next/cache", () => ({ cacheLife }));

// The logo route (D-154): the server fetches CFBD's 500px PNG and returns a 40px PNG from the
// app's own origin, cached for a month, so the browser never asks CFBD (D-101).

const PNG_SIGNATURE = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

/** Width and height from a PNG's IHDR chunk. */
function pngSize(bytes: Uint8Array) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  return { width: view.getUint32(16), height: view.getUint32(20) };
}

// A real 500x500 PNG stands in for CFBD's.
async function sourcePng() {
  const { ImageResponse } = await import("next/og");
  const square = createElement("div", { style: { width: "100%", height: "100%", background: "red" } });
  return new Uint8Array(await new ImageResponse(square, { width: 500, height: 500 }).arrayBuffer());
}

const call = (file: string) => GET(new Request(`http://app.test/logos/${file}`), { params: Promise.resolve({ file }) });

afterEach(() => {
  vi.unstubAllGlobals();
  cacheLife.mockClear();
});

describe("GET /logos/[file]", () => {
  it("returns a 40px PNG with a month-long public cache, fetched from CFBD on the server", async () => {
    const source = await sourcePng();
    const fetchMock = vi.fn(async () => new Response(source, { headers: { "content-type": "image/png" } }));
    vi.stubGlobal("fetch", fetchMock);

    const res = await call("194.png");

    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("image/png");
    expect(res.headers.get("cache-control")).toBe("public, max-age=2678400, s-maxage=2678400, immutable");
    const bytes = new Uint8Array(await res.arrayBuffer());
    expect([...bytes.slice(0, 8)]).toEqual(PNG_SIGNATURE);
    expect(pngSize(bytes)).toEqual({ width: LOGO_PX, height: LOGO_PX });
    expect(bytes.byteLength).toBeLessThan(source.byteLength);
    expect(cacheLife).toHaveBeenCalledExactlyOnceWith("max");
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(String((fetchMock.mock.calls[0] as unknown[])[0])).toBe("https://cdn.collegefootballdata.com/logos/500/194.png");
  }, 30_000);

  it("is 404 for a name that isn't <id>.png, without fetching anything", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    for (const file of ["194", "x.png", "..%2F194.png", "194.svg"]) {
      expect((await call(file)).status).toBe(404);
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("is 404 when CFBD has no such logo", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("no", { status: 403 })));
    const res = await call("999999.png");
    expect(res.status).toBe(404);
    expect(res.headers.get("cache-control")).toBe("no-store");
    // A miss is kept only briefly, so a CDN hiccup doesn't stick for a month.
    expect(cacheLife).toHaveBeenCalledExactlyOnceWith("minutes");
  });

  it("is 404 when CFBD can't be reached", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("fetch failed"))));
    expect((await call("194.png")).status).toBe(404);
  });

  it("is 404 when CFBD answers something other than a PNG", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>", { headers: { "content-type": "text/html" } })));
    expect((await call("194.png")).status).toBe(404);
  });
});
