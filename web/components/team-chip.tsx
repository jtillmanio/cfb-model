import Image from "next/image";

import { logoPath } from "@/lib/logos";
import { cn } from "@/lib/utils";

// TeamChip (design/README.md › Components; Components.dc.html › Team chip). The 20px logo slot is
// the only place a team's colour appears (D-075): the logo when CFBD has one (D-146), else a dot
// in the team colour. The browser asks the app's own /logos/<id>.png, never CFBD's CDN (D-101,
// D-154); a logo URL that route doesn't serve draws the dot. Locked games drop the colour.

type TeamChipProps = {
  abbreviation: string;
  /** The school's full name, shown instead of the abbreviation when `full` is set. */
  school?: string;
  full?: boolean;
  /** `teams.logo_url`; null (or a URL `/logos` doesn't serve) draws the colour dot. */
  logoUrl: string | null;
  /** `teams.color`, e.g. `#BB0000`; null draws a muted dot. */
  color: string | null;
  /** The model's rank, printed small and muted before the name, with no "#". */
  rank?: number | null;
  fcs?: boolean;
  /** Neutral site: an "N" marker after the name. */
  neutral?: boolean;
  /** Kickoff has passed: the slot loses its colour and the text goes to the locked token. */
  locked?: boolean;
  className?: string;
};

/** A small outlined tag after the name (FCS, N). */
function Tag({ children, title }: { children: string; title?: string }) {
  return (
    <span
      title={title}
      className="inline-flex h-4.5 shrink-0 items-center rounded-sm border px-1.25 text-caption text-muted-foreground"
    >
      {children}
    </span>
  );
}

export function TeamChip({
  abbreviation,
  school,
  full,
  logoUrl,
  color,
  rank,
  fcs,
  neutral,
  locked,
  className,
}: TeamChipProps) {
  const name = full && school ? school : abbreviation;
  const teamColor = locked ? null : color;
  const logo = logoPath(logoUrl);

  return (
    <span
      data-slot="team-chip"
      className={cn(
        "inline-flex h-7 min-w-0 items-center gap-1.5 rounded-sm px-1.5",
        locked && "text-locked",
        className,
      )}
    >
      {logo ? (
        // The route already serves the 2x size, so next/image only draws the <img>.
        <Image
          src={logo}
          unoptimized
          alt=""
          width={20}
          height={20}
          className={cn("size-5 shrink-0 object-contain", locked && "opacity-60 grayscale")}
        />
      ) : (
        <span
          data-slot="team-dot"
          aria-hidden
          className={cn("size-5 shrink-0 rounded-full ring-1 ring-border", !teamColor && "bg-muted")}
          style={teamColor ? { backgroundColor: teamColor } : undefined}
        />
      )}
      {rank != null && <span className="text-caption text-muted-foreground">{rank}</span>}
      <span className="truncate font-medium">{name}</span>
      {fcs && <Tag>FCS</Tag>}
      {neutral && <Tag title="Neutral site">N</Tag>}
    </span>
  );
}
