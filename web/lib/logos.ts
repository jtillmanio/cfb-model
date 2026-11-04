// Team logos (D-146, D-154). Staging stores CFBD's `logos[0]` in `teams.logo_url`, a 500px PNG on
// CFBD's CDN. The browser never fetches it (D-101): the chip asks the app's own /logos/<id>.png,
// whose route fetches the CDN on the server, renders it at LOGO_PX and lets Vercel's CDN keep it.

/** The only logo URLs the route serves: CFBD's 500px light logo, by team id. */
const CFBD_LOGO = /^https:\/\/cdn\.collegefootballdata\.com\/logos\/500\/(\d{1,6})\.png$/;

/** `<id>.png`, the route's one segment. */
const LOGO_FILE = /^(\d{1,6})\.png$/;

/** The rendered size: the chip's 20px slot at 2x. */
export const LOGO_PX = 40;

/** A month: logos change about once a season. */
export const LOGO_MAX_AGE = 2_678_400;

/** The app path for a team's logo, or null when the route doesn't serve it (the chip draws the dot). */
export function logoPath(logoUrl: string | null): string | null {
  const id = logoUrl ? CFBD_LOGO.exec(logoUrl)?.[1] : undefined;
  return id ? `/logos/${id}.png` : null;
}

/** The team id in a `/logos/[file]` segment, or null when it isn't `<digits>.png`. */
export function logoFileId(file: string): string | null {
  return LOGO_FILE.exec(file)?.[1] ?? null;
}

/** The CDN URL the route fetches for a team id. */
export function cfbdLogoUrl(id: string): string {
  return `https://cdn.collegefootballdata.com/logos/500/${id}.png`;
}
