import { afterEach, describe, expect, it, vi } from "vitest";

import {
  continuePath,
  deniedLoginUrl,
  LOGIN_COPY,
  loginState,
  raceWakeNote,
  safeNextPath,
  WAKE_NOTE_AFTER_MS,
} from "./login";

describe("loginState", () => {
  it("is the default card with no error", () => {
    expect(loginState({}, true)).toEqual({ kind: "default" });
  });

  it("is denied with the GitHub login the refused sign-in carried", () => {
    expect(loginState({ error: "AccessDenied", login: "someone-else" }, true)).toEqual({
      kind: "denied",
      login: "someone-else",
    });
  });

  it("is denied without a name when the login is missing or isn't a GitHub login", () => {
    expect(loginState({ error: "AccessDenied" }, true)).toEqual({ kind: "denied", login: null });
    for (const login of ["", "<b>x</b>", "a".repeat(40), "two words", "x/../y"]) {
      expect(loginState({ error: "AccessDenied", login }, true)).toEqual({
        kind: "denied",
        login: null,
      });
    }
  });

  it("reads the first value of a repeated parameter", () => {
    expect(loginState({ error: ["AccessDenied", "x"], login: ["first", "second"] }, true)).toEqual(
      { kind: "denied", login: "first" },
    );
  });

  it("falls back to the default card for an error it doesn't know", () => {
    expect(loginState({ error: "Configuration" }, true)).toEqual({ kind: "default" });
    expect(loginState({ error: "OAuthCallbackError", login: "someone" }, true)).toEqual({
      kind: "default",
    });
  });

  it("is unavailable when no GitHub client ID is configured (previews, D-102), whatever the URL says", () => {
    expect(loginState({}, false)).toEqual({ kind: "unavailable" });
    expect(loginState({ error: "AccessDenied", login: "someone-else" }, false)).toEqual({
      kind: "unavailable",
    });
  });
});

describe("LOGIN_COPY", () => {
  it("uses the design's copy, with no number in the waking note (D-097)", () => {
    expect(LOGIN_COPY.deniedBody("someone-else")).toBe(
      "You're signed in to GitHub as someone-else. Only the one allowlisted account can use this app.",
    );
    expect(LOGIN_COPY.footnote).toBe("Stays signed in on this device for 90 days.");
    expect(LOGIN_COPY.wakingNote).not.toMatch(/\d/);
  });
});

describe("deniedLoginUrl", () => {
  it("carries the refused GitHub login to /login", () => {
    expect(deniedLoginUrl("someone-else")).toBe("/login?error=AccessDenied&login=someone-else");
  });

  it("leaves the login out when there isn't one", () => {
    expect(deniedLoginUrl(undefined)).toBe("/login?error=AccessDenied");
    expect(deniedLoginUrl("")).toBe("/login?error=AccessDenied");
  });
});

describe("safeNextPath", () => {
  it("keeps a path on this site, with its query and hash", () => {
    expect(safeNextPath("/teams")).toBe("/teams");
    expect(safeNextPath("/teams?season=2025#ohio-state")).toBe("/teams?season=2025#ohio-state");
  });

  it("reduces an absolute URL (Auth.js's callbackUrl) to its path", () => {
    expect(safeNextPath("http://127.0.0.1:3100/teams?x=1")).toBe("/teams?x=1");
    expect(safeNextPath("https://evil.example/teams")).toBe("/teams");
  });

  it("never returns a protocol-relative path", () => {
    expect(safeNextPath("//evil.example/x")).toBe("/x");
    expect(safeNextPath("/\\evil.example/x")).toBe("/x");
    expect(safeNextPath("http://127.0.0.1//evil.example/x")).toBe("/");
  });

  it("falls back to / when missing, unparsable, or back into sign-in", () => {
    expect(safeNextPath(undefined)).toBe("/");
    expect(safeNextPath("")).toBe("/");
    expect(safeNextPath("http://[bad")).toBe("/");
    expect(safeNextPath("/login")).toBe("/");
    expect(safeNextPath("/login?error=AccessDenied")).toBe("/");
    expect(safeNextPath("/login/continue?to=/teams")).toBe("/");
    expect(safeNextPath("/loginx")).toBe("/loginx");
  });

  it("reads the first value of a repeated parameter", () => {
    expect(safeNextPath(["/teams", "/other"])).toBe("/teams");
  });
});

describe("continuePath", () => {
  it("sends the sign-in through /login/continue with the encoded target", () => {
    expect(continuePath("/teams?season=2025")).toBe("/login/continue?to=%2Fteams%3Fseason%3D2025");
  });
});

describe("raceWakeNote", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("waits 1.5 s before the note (D-072)", () => {
    expect(WAKE_NOTE_AFTER_MS).toBe(1500);
  });

  it("is ready when the database answers before the note is due", async () => {
    vi.useFakeTimers();
    const health = new Promise((resolve) => setTimeout(resolve, WAKE_NOTE_AFTER_MS - 1));
    const result = raceWakeNote(health);
    await vi.advanceTimersByTimeAsync(WAKE_NOTE_AFTER_MS);
    expect(await result).toBe("ready");
  });

  it("is ready when the call fails fast: the target page shows its own error", async () => {
    expect(await raceWakeNote(Promise.reject(new Error("refused")))).toBe("ready");
  });

  it("is waking when the database hasn't answered after 1.5 s", async () => {
    vi.useFakeTimers();
    const health = new Promise((resolve) => setTimeout(resolve, 5000));
    const result = raceWakeNote(health);
    await vi.advanceTimersByTimeAsync(WAKE_NOTE_AFTER_MS);
    expect(await result).toBe("waking");
  });
});
