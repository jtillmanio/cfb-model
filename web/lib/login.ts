// S-15 sign-in (TASK-002, F-42 items 1 and 3): which card /login draws, its copy, and where a
// sign-in goes next. Pure, so the page and the Auth.js callbacks share it.

// "Waking up the database…" appears after 1.5 s without an answer (D-072).
export const WAKE_NOTE_AFTER_MS = 1500;

// Copy from the App States boards (frame "login"). The footnote says "device" at every width
// (AC-1); the waking note gives no number (D-097). The preview note isn't in the design (D-102).
export const LOGIN_COPY = {
  wordmark: "CFB Model",
  heading: "Sign in",
  subhead: "Private app · one GitHub account",
  signIn: "Sign in with GitHub",
  footnote: "Stays signed in on this device for 90 days.",
  deniedTitle: "This GitHub account isn't allowed",
  deniedBody: (login: string | null) =>
    `${login ? `You're signed in to GitHub as ${login}. ` : ""}Only the one allowlisted account can use this app.`,
  useOther: "Use a different account",
  wakingTitle: "Waking up the database…",
  wakingNote: "GitHub said yes. The first request after a quiet spell can take a few seconds.",
  unavailable: "Sign-in isn't available on preview deployments.",
} as const;

export type LoginState =
  | { kind: "default" }
  | { kind: "denied"; login: string | null }
  | { kind: "unavailable" };

type Param = string | string[] | undefined;

function first(value: Param): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

// GitHub logins are letters, digits and hyphens, at most 39 characters. Anything else in the URL
// was typed by hand, so the name is left out rather than echoed.
const GITHUB_LOGIN = /^[A-Za-z0-9-]{1,39}$/;

export function loginState(
  params: { error?: Param; login?: Param },
  githubConfigured: boolean,
): LoginState {
  if (!githubConfigured) return { kind: "unavailable" };
  if (first(params.error) !== "AccessDenied") return { kind: "default" };
  const login = first(params.login);
  return { kind: "denied", login: login && GITHUB_LOGIN.test(login) ? login : null };
}

// Where Auth.js sends a refused GitHub account: the signIn callback returns this instead of false.
export function deniedLoginUrl(login: string | undefined): string {
  const params = new URLSearchParams({ error: "AccessDenied" });
  if (login) params.set("login", login);
  return `/login?${params}`;
}

// The page to open after sign-in, as a path on this site. Auth.js's callbackUrl is absolute, and
// anything in the URL can be typed by hand: keep only the path, never a protocol-relative one,
// and never back into sign-in.
export function safeNextPath(raw: Param): string {
  const value = first(raw);
  if (!value) return "/";
  let url: URL;
  try {
    url = new URL(value, "http://localhost");
  } catch {
    return "/";
  }
  const path = `${url.pathname}${url.search}${url.hash}`;
  if (path.startsWith("//")) return "/";
  if (url.pathname === "/login" || url.pathname.startsWith("/login/")) return "/";
  return path;
}

// Sign-in returns through /login/continue, which shows the waking card if the database is slow.
export function continuePath(next: string): string {
  return `/login/continue?to=${encodeURIComponent(next)}`;
}

// "ready" if the call settles (either way) before the note is due, else "waking".
export async function raceWakeNote(
  call: Promise<unknown>,
  ms: number = WAKE_NOTE_AFTER_MS,
): Promise<"ready" | "waking"> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const due = new Promise<"waking">((resolve) => {
    timer = setTimeout(() => resolve("waking"), ms);
  });
  const settled = call.then(
    () => "ready" as const,
    () => "ready" as const,
  );
  try {
    return await Promise.race([settled, due]);
  } finally {
    clearTimeout(timer);
  }
}
