// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DesignSystem from "./page";

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe("/design-system (D-152)", () => {
  it("404s when VERCEL_ENV is production", () => {
    vi.stubEnv("VERCEL_ENV", "production");
    // notFound() throws an error whose digest marks it as a 404.
    expect(() => DesignSystem()).toThrow(
      expect.objectContaining({ digest: expect.stringContaining("404") }),
    );
  });

  for (const env of ["preview", "development", undefined]) {
    it(`renders every component state in both themes when VERCEL_ENV is ${env ?? "unset"}`, () => {
      if (env) vi.stubEnv("VERCEL_ENV", env);
      render(<DesignSystem />);

      for (const theme of ["Dark", "Light"]) {
        const panel = screen.getByRole("region", { name: theme });
        // Edge pill: pick, below threshold, exactly the threshold, no line, locked.
        expect(within(panel).getByText("+3.7 OSU")).toBeTruthy();
        expect(within(panel).getByText("+0.6 UTAH")).toBeTruthy();
        expect(within(panel).getByText("+2.5 OSU")).toBeTruthy();
        expect(within(panel).getByText("+0.9 UNLV")).toBeTruthy();
        // Tier badge: A, B, C, no pick, labelled.
        for (const letter of ["A", "B", "C"]) expect(within(panel).getAllByText(letter).length).toBeGreaterThan(0);
        expect(within(panel).getByText("Tier A")).toBeTruthy();
        // Result marker, all four states.
        for (const label of ["Covered", "Not covered", "Push", "Pending"]) {
          expect(within(panel).getAllByText(label).length).toBeGreaterThan(0);
        }
        // Filter chips, one selected.
        const chips = within(panel).getByRole("group", { name: `${theme.toLowerCase()} filters` });
        expect(within(chips).getAllByRole("button")).toHaveLength(4);
        expect(within(chips).getByRole("button", { name: "Picks only" }).getAttribute("aria-pressed")).toBe("true");
      }
    });
  }
});
