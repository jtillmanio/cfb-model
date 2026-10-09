import { describe, expect, it } from "vitest";

import { isAllowedGitHubId } from "./allowlist";

describe("isAllowedGitHubId", () => {
  it("admits the allowlisted ID", () => {
    expect(isAllowedGitHubId("1234567", "1234567")).toBe(true);
  });

  it("admits a numeric ID, the type GitHub's profile carries", () => {
    expect(isAllowedGitHubId(1234567, "1234567")).toBe(true);
  });

  it("tolerates whitespace around the configured ID", () => {
    expect(isAllowedGitHubId("1234567", " 1234567\n")).toBe(true);
  });

  it("refuses any other ID", () => {
    expect(isAllowedGitHubId("7654321", "1234567")).toBe(false);
    expect(isAllowedGitHubId("12345678", "1234567")).toBe(false);
  });

  it("refuses everyone when the allowlist is unset (fail closed)", () => {
    expect(isAllowedGitHubId("1234567", undefined)).toBe(false);
  });

  it("refuses everyone when the allowlist is empty or blank (fail closed)", () => {
    expect(isAllowedGitHubId("1234567", "")).toBe(false);
    expect(isAllowedGitHubId("", "")).toBe(false);
    expect(isAllowedGitHubId("1234567", "   ")).toBe(false);
  });

  it("refuses a missing ID", () => {
    expect(isAllowedGitHubId(undefined, "1234567")).toBe(false);
    expect(isAllowedGitHubId(null, "1234567")).toBe(false);
  });
});
