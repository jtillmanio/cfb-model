// Team logos (D-146, D-154, D-173). Staging stores CFBD's `logos[0]` in `teams.logo_url`, a 500px
// PNG on CFBD's CDN. The browser never fetches it (D-101): the chip asks the app's own
// /logos/<id>.png, a static 40px file in web/public/logos that `pnpm --dir web logos` writes, so
// Vercel's CDN serves it and no function runs. logo-ids.json lists the ids that have a file.

import LOGO_IDS from "./logo-ids.json";

/** The only logo URLs the chip maps: CFBD's 500px light logo, by team id. */
const CFBD_LOGO = /^https:\/\/cdn\.collegefootballdata\.com\/logos\/500\/(\d{1,6})\.png$/;

/** The ids with a file in web/public/logos. */
const HAS_FILE = new Set<number>(LOGO_IDS);

/** The rendered size: the chip's 20px slot at 2x (web/scripts/logos.mjs renders at this). */
export const LOGO_PX = 40;

/** The app path for a team's logo, or null when there is no file for it (the chip draws the dot). */
export function logoPath(logoUrl: string | null): string | null {
  const id = logoUrl ? CFBD_LOGO.exec(logoUrl)?.[1] : undefined;
  return id && HAS_FILE.has(Number(id)) ? `/logos/${id}.png` : null;
}
