import type { components } from "./api-types";

// Generated from the API's response models (`pnpm api:types`, D-011); these are aliases.
export type Team = components["schemas"]["TeamOut"];
export type TeamsResponse = components["schemas"]["TeamsOut"];

const collator = new Intl.Collator("en", { sensitivity: "base" });

function compareConference(a: string | null, b: string | null): number {
  if (a === b) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return collator.compare(a, b);
}

/** The skeleton's Teams index order: conference, then school. Teams with no conference last. */
export function sortTeams(teams: readonly Team[]): Team[] {
  return [...teams].sort(
    (a, b) => compareConference(a.conference, b.conference) || collator.compare(a.school, b.school),
  );
}
