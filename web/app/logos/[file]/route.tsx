import { cacheLife } from "next/cache";
import { ImageResponse } from "next/og";

import { cfbdLogoUrl, LOGO_MAX_AGE, LOGO_PX, logoFileId } from "@/lib/logos";

// GET /logos/<id>.png (D-154): a team logo from the app's own origin, so the browser never asks
// CFBD's CDN (D-101). The server fetches CFBD's 500px PNG once, renders it at 40px (the 20px slot
// at 2x) and caches the result; the month-long Cache-Control lets Vercel's CDN keep it too. The
// path ends in .png, so proxy.ts's matcher skips it: logos are public, and an image request never
// gets a sign-in redirect. Vercel's /_next/image isn't used: under the services setup in vercel.json
// it reached the web service and came back 404.

/** CFBD's logo for a team id, rendered at LOGO_PX; null when CFBD has no PNG for it. A logo is
 *  kept for the longest lifetime, a miss only for minutes, so a CDN hiccup doesn't stick. */
async function renderLogo(id: string): Promise<Uint8Array | null> {
  "use cache";
  const upstream = await fetch(cfbdLogoUrl(id), { signal: AbortSignal.timeout(10_000) }).catch(() => null);
  if (!upstream?.ok || upstream.headers.get("content-type")?.split(";")[0] !== "image/png") {
    cacheLife("minutes");
    return null;
  }
  cacheLife("max");
  const src = `data:image/png;base64,${Buffer.from(await upstream.arrayBuffer()).toString("base64")}`;
  const image = new ImageResponse(
    // Satori draws an <img>, not the DOM; next/image doesn't apply here.
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt="" width={LOGO_PX} height={LOGO_PX} style={{ objectFit: "contain" }} />,
    { width: LOGO_PX, height: LOGO_PX },
  );
  return new Uint8Array(await image.arrayBuffer());
}

const notFound = () => new Response("Not found", { status: 404, headers: { "cache-control": "no-store" } });

export async function GET(_request: Request, { params }: { params: Promise<{ file: string }> }) {
  const id = logoFileId((await params).file);
  if (!id) return notFound();
  const png = await renderLogo(id);
  if (!png) return notFound();
  return new Response(png as Uint8Array<ArrayBuffer>, {
    headers: {
      "content-type": "image/png",
      "cache-control": `public, max-age=${LOGO_MAX_AGE}, s-maxage=${LOGO_MAX_AGE}, immutable`,
    },
  });
}
