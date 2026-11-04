import { afterEach, describe, expect, it, vi } from "vitest";

import { previewUserId } from "./preview";

const ALLOWED = "1234567";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("previewUserId", () => {
  it("is the allowlisted GitHub ID on a Vercel preview (TASK-059 AC-1)", () => {
    vi.stubEnv("VERCEL_ENV", "preview");
    vi.stubEnv("AUTH_ALLOWED_GITHUB_ID", ALLOWED);
    expect(previewUserId()).toBe(ALLOWED);
  });

  it("trims the allowlisted ID, as the allowlist check does", () => {
    vi.stubEnv("VERCEL_ENV", "preview");
    vi.stubEnv("AUTH_ALLOWED_GITHUB_ID", ` ${ALLOWED} `);
    expect(previewUserId()).toBe(ALLOWED);
  });

  it.each([
    ["unset", undefined],
    ["empty", ""],
    ["blank", "   "],
  ])("is null on a preview when the allowlist is %s (AC-2)", (_label, value) => {
    vi.stubEnv("VERCEL_ENV", "preview");
    vi.stubEnv("AUTH_ALLOWED_GITHUB_ID", value);
    expect(previewUserId()).toBeNull();
  });

  it.each([
    ["unset", undefined],
    ["development", "development"],
    ["production", "production"],
    ["Preview (wrong case)", "Preview"],
  ])("is null when VERCEL_ENV is %s (AC-3)", (_label, value) => {
    vi.stubEnv("VERCEL_ENV", value);
    vi.stubEnv("AUTH_ALLOWED_GITHUB_ID", ALLOWED);
    expect(previewUserId()).toBeNull();
  });
});
