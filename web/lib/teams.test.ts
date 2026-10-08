import { describe, expect, it } from "vitest";

import { sortTeams, type Team } from "./teams";

const team = (school: string, conference: string | null): Team => ({
  id: school.length,
  school,
  abbreviation: null,
  conference,
  color: null,
});

describe("sortTeams", () => {
  it("orders by conference, then school", () => {
    const sorted = sortTeams([
      team("Texas", "SEC"),
      team("Penn State", "Big Ten"),
      team("Georgia", "SEC"),
      team("Ohio State", "Big Ten"),
      team("Utah", "Big 12"),
    ]);
    expect(sorted.map((t) => t.school)).toEqual([
      "Utah",
      "Ohio State",
      "Penn State",
      "Georgia",
      "Texas",
    ]);
  });

  it("puts teams with no conference last", () => {
    const sorted = sortTeams([team("Army", null), team("Akron", "MAC"), team("Navy", "AAC")]);
    expect(sorted.map((t) => t.school)).toEqual(["Navy", "Akron", "Army"]);
  });

  it("ignores case when comparing school names", () => {
    const sorted = sortTeams([team("ohio", "MAC"), team("Akron", "MAC")]);
    expect(sorted.map((t) => t.school)).toEqual(["Akron", "ohio"]);
  });

  it("does not reorder the array it was given", () => {
    const input = [team("Texas", "SEC"), team("Utah", "Big 12")];
    sortTeams(input);
    expect(input.map((t) => t.school)).toEqual(["Texas", "Utah"]);
  });
});
