import { describe, expect, it } from "vitest";

import {
  formatClv,
  formatCoverPct,
  formatEdge,
  formatFinal,
  formatGameClock,
  formatKickoff,
  formatLiveScore,
  formatLockCountdown,
  formatModelLine,
  formatPrice,
  formatRankMove,
  formatRating,
  formatRecord,
  formatSpread,
  formatUnits,
  formatWinPct,
  formatWinRate,
} from "./format";

const PAD = "  ";

describe("number-format card", () => {
  it.each([
    ["spread, home favorite", () => formatSpread(-27.5, "OSU", "MICH"), "OSU −27.5"],
    ["spread, away favorite", () => formatSpread(6.5, "OSU", "MICH"), "MICH −6.5"],
    ["spread, whole number is bare", () => formatSpread(-10, "BSU", "UNLV"), "BSU −10"],
    ["spread, pick'em", () => formatSpread(0, "OSU", "MICH"), "PK"],
    ["spread, no line", () => formatSpread(null, "OSU", "MICH"), "No line"],
    ["price", () => formatPrice(-110), "−110"],
    ["price, plus money", () => formatPrice(150), "+150"],
    ["model line, always one decimal", () => formatModelLine(34, "CLEM", "WAKE"), "CLEM −34.0"],
    ["model line, away favored", () => formatModelLine(-3.25, "OSU", "MICH"), "MICH −3.3"],
    ["edge toward home", () => formatEdge(3.7, "OSU", "MICH"), "+3.7 OSU"],
    ["edge toward away", () => formatEdge(-2.5, "OSU", "MICH"), "+2.5 MICH"],
    ["edge, no line", () => formatEdge(null, "OSU", "MICH"), "—"],
    ["cover %", () => formatCoverPct(0.59), "59%"],
    ["cover %, market implied", () => formatCoverPct(0.54, { marketImplied: true }), "~54%"],
    ["win %, home favorite", () => formatWinPct(0.54, "TEX", "OU"), "TEX 54%"],
    ["win %, away favorite", () => formatWinPct(0.4, "TEX", "OU"), "OU 60%"],
    ["win rate", () => formatWinRate(0.564), "56.4%"],
    ["rating", () => formatRating(27.4), "+27.4"],
    ["rank move up", () => formatRankMove(3), "▲3"],
    ["rank move down", () => formatRankMove(-1), "▼1"],
    ["rank move, unchanged", () => formatRankMove(0), "—"],
    ["rank move, unranked", () => formatRankMove(null), "—"],
    ["record with a push", () => formatRecord(31, 24, 1), "31-24-1"],
    ["record without a push", () => formatRecord(5, 0), "5-0"],
    ["units, win", () => formatUnits(4.6), "+4.6u"],
    ["units, loss", () => formatUnits(-1.1), "−1.1u"],
    ["CLV", () => formatClv(0.9), "+0.9 pts"],
  ])("%s", (_name, run, expected) => {
    expect(run()).toBe(expected);
  });
});

describe("minus sign and zero", () => {
  const negatives = [-0.04, -0.05, -1, -1.1, -9.5, -27.5, -110];

  it("never prints a hyphen-minus for a negative number", () => {
    for (const n of negatives) {
      const outputs = [
        formatSpread(n, "OSU", "MICH"),
        formatSpread(-n, "OSU", "MICH"),
        formatSpread(n, "OSU", "MICH", { align: true }),
        formatModelLine(n, "OSU", "MICH"),
        formatModelLine(-n, "OSU", "MICH"),
        formatPrice(n),
        formatEdge(n, "OSU", "MICH"),
        formatEdge(-n, "OSU", "MICH"),
        formatRating(n),
        formatRankMove(n),
        formatUnits(n),
        formatClv(n),
      ];
      for (const out of outputs) expect(out, `${n}`).not.toContain("-");
    }
    // The minus is the true minus sign.
    expect(formatSpread(-27.5, "OSU", "MICH")).toContain("−");
    expect(formatUnits(-1.1)).toContain("−");
    expect(formatClv(-0.4)).toBe("−0.4 pts");
    expect(formatRating(-3.2)).toBe("−3.2");
  });

  it("never prints negative zero", () => {
    expect(formatRating(-0.04)).toBe("0.0");
    expect(formatUnits(-0.04)).toBe("0.0u");
    expect(formatClv(-0.04)).toBe("0.0 pts");
    expect(formatEdge(-0.04, "OSU", "MICH")).toBe("0.0");
    expect(formatSpread(-0, "OSU", "MICH")).toBe("PK");
    expect(formatModelLine(-0.04, "OSU", "MICH")).toBe("PK");
    expect(formatModelLine(0.04, "OSU", "MICH")).toBe("PK");
  });
});

describe("spread alignment", () => {
  it("pads a whole-number spread with U+2008 U+2007 when asked", () => {
    expect(formatSpread(-10, "BSU", "UNLV", { align: true })).toBe(`BSU −10${PAD}`);
    expect(formatSpread(-10, "BSU", "UNLV", { align: true })).toHaveLength("BSU −10".length + 2);
  });

  it("returns a whole-number spread bare without the flag", () => {
    expect(formatSpread(-10, "BSU", "UNLV")).toBe("BSU −10");
    expect(formatSpread(-10, "BSU", "UNLV", { align: false })).toBe("BSU −10");
  });

  it("leaves a half-point spread unchanged with the flag", () => {
    expect(formatSpread(-9.5, "BSU", "UNLV", { align: true })).toBe("BSU −9.5");
  });

  it("never pads a model line", () => {
    expect(formatModelLine(34, "CLEM", "WAKE")).toBe("CLEM −34.0");
  });
});

describe("kickoff", () => {
  const kickoff = "2026-10-10T19:30:00Z";

  it("formats Eastern time with the zone label", () => {
    expect(formatKickoff(kickoff, "2026-10-10", { zone: "America/New_York" })).toBe("Sat 3:30 PM ET");
  });

  it("drops the zone label inside a table", () => {
    expect(formatKickoff(kickoff, "2026-10-10", { zone: "America/New_York", inTable: true })).toBe("Sat 3:30 PM");
  });

  it("converts to Central time", () => {
    expect(formatKickoff(kickoff, "2026-10-10", { zone: "America/Chicago" })).toBe("Sat 2:30 PM CT");
  });

  it("moves to the local weekday when the zone crosses midnight", () => {
    expect(formatKickoff("2026-10-11T02:00:00Z", "2026-10-10", { zone: "America/New_York" })).toBe("Sat 10:00 PM ET");
  });

  it("says TBA when the kickoff is unknown", () => {
    expect(formatKickoff(null, "2026-10-10", { zone: "America/New_York" })).toBe("Sat TBA");
    expect(formatKickoff(null, "2026-10-11", { zone: "America/Chicago" })).toBe("Sun TBA");
  });
});

describe("lock countdown", () => {
  const kickoff = "2026-10-10T19:30:00Z";
  const before = (ms: number) => new Date(Date.parse(kickoff) - ms);
  const D = 86_400_000;
  const H = 3_600_000;
  const M = 60_000;

  it("shows the two largest units", () => {
    expect(formatLockCountdown(kickoff, before(1 * D + 14 * H + 5 * M))).toBe("Locks in 1d 14h");
    expect(formatLockCountdown(kickoff, before(3 * H + 20 * M + 40_000))).toBe("Locks in 3h 20m");
    expect(formatLockCountdown(kickoff, before(12 * M + 30_000))).toBe("Locks in 12m");
  });

  it("says under a minute when less than one minute is left", () => {
    expect(formatLockCountdown(kickoff, before(30_000))).toBe("Locks in <1m");
  });

  it("says Locked at or after kickoff", () => {
    expect(formatLockCountdown(kickoff, before(0))).toBe("Locked");
    expect(formatLockCountdown(kickoff, before(-5 * M))).toBe("Locked");
  });
});

describe("live and final", () => {
  it("prints the live score with the away team first", () => {
    expect(formatLiveScore("PUR", 3, "OSU", 24)).toBe("PUR 3 · OSU 24");
  });

  it("prints the game clock", () => {
    expect(formatGameClock(3, 9 * 60 + 12)).toBe("Q3 9:12");
    expect(formatGameClock(1, 5)).toBe("Q1 0:05");
    expect(formatGameClock(5, 60)).toBe("OT 1:00");
    expect(formatGameClock(6, 0)).toBe("2OT 0:00");
  });

  it("prints the final", () => {
    expect(formatFinal("UNLV", 24, "BSU", 31)).toBe("Final · UNLV 24, BSU 31");
  });
});
