import { describe, expect, it } from "vitest";

import { cfbdLogoUrl, logoFileId, logoPath, LOGO_PX } from "./logos";

// Team logos are served from the app's own /logos/<id>.png (D-154), never CFBD's CDN (D-101).
describe("logoPath", () => {
  it("maps CFBD's logo URL to the app's own route", () => {
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
});

describe("logoFileId", () => {
  it("accepts only <digits>.png and returns the id", () => {
    expect(logoFileId("194.png")).toBe("194");
    for (const bad of ["194", "194.jpg", "abc.png", "../194.png", "194.png.png", "", "1234567.png"]) {
      expect(logoFileId(bad)).toBeNull();
    }
  });
});

describe("cfbdLogoUrl", () => {
  it("builds the one CDN URL the route fetches", () => {
    expect(cfbdLogoUrl("194")).toBe("https://cdn.collegefootballdata.com/logos/500/194.png");
  });

  it("serves the 20px slot at 2x", () => {
    expect(LOGO_PX).toBe(40);
  });
});
