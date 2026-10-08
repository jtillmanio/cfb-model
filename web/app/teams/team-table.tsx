import type { ReactNode } from "react";

import type { Team } from "@/lib/teams";

// Teams index (S-17), skeleton cut: team chip, school and conference only (02 › Walking skeleton).
// Grammar from Teams Desktop / Teams Mobile: a bordered card, 40px header, 48px rows,
// 12px cell padding, caption footer.

export function TeamsPage({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-[1216px] px-4 py-6 md:px-6 xl:px-8">
      <header className="mb-6 flex flex-col gap-1 md:flex-row md:items-baseline md:gap-4">
        <h1 className="text-section font-semibold tracking-[-0.005em] md:text-title">Teams</h1>
        <p className="text-caption text-muted-foreground md:text-body">{caption}</p>
      </header>
      {children}
    </main>
  );
}

export function TeamDot({ color }: { color: string | null }) {
  // Brand color only as the 20px dot (design/README.md › Color rules); none known -> outline.
  return (
    <span
      aria-hidden
      className="size-5 shrink-0 rounded-full border border-border"
      style={color ? { backgroundColor: color, borderColor: color } : undefined}
    />
  );
}

export function TeamTable({ teams }: { teams: Team[] }) {
  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <table className="w-full border-collapse text-left">
        <thead className="text-caption font-medium text-muted-foreground">
          <tr className="h-10 border-b">
            <th scope="col" className="px-3 pl-4 font-medium md:pl-14">
              Team
            </th>
            <th scope="col" className="hidden w-48 px-3 font-medium md:table-cell">
              Conf
            </th>
          </tr>
        </thead>
        <tbody>
          {teams.map((team) => (
            <tr key={team.id} className="h-12 border-b last:border-b-0 hover:bg-accent">
              <td className="px-3 py-2 pl-4">
                <div className="flex items-center gap-4">
                  <TeamDot color={team.color} />
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate font-semibold">{team.school}</span>
                    <span className="text-caption text-muted-foreground md:hidden">
                      {team.conference ?? "—"}
                    </span>
                  </div>
                </div>
              </td>
              <td className="hidden px-3 text-muted-foreground md:table-cell">
                {team.conference ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t px-4 py-3 text-caption text-muted-foreground">
        Showing {teams.length} · FBS · sorted by conference
      </p>
    </div>
  );
}

export function EmptyTeams() {
  return (
    <div className="flex flex-col items-center gap-1 rounded-lg border bg-card px-4 py-16 text-center">
      <p className="text-panel font-semibold">No teams yet</p>
      <p className="text-caption text-muted-foreground">
        Teams appear after the first data sync.
      </p>
    </div>
  );
}
