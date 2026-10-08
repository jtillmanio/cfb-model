export type Team = {
  id: number;
  school: string;
  abbreviation: string | null;
  conference: string | null;
  color: string | null;
};

export type TeamsResponse = {
  season: number | null;
  teams: Team[];
};

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
