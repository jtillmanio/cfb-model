import { Lock } from "lucide-react";

import { formatEdge } from "@/lib/format";

import { Badge } from "./ui/badge";

// EdgePill (design/README.md › Components › Numbers & badges; D-061).
// Filled `--edge` only when the edge clears the pick threshold, plain muted text below it.
// The threshold is a prop: the active version's spec owns it (D-055), never this file.
// The pill takes no hover or focus of its own; the row is the hit target.

type EdgePillProps = {
  /** `edge_pts`: positive likes home, negative likes away; null when there is no line. */
  edgePts: number | null;
  home: string;
  away: string;
  /** Smallest |edge| that makes a pick. */
  threshold: number;
  /** The game has started: muted fill, lock icon. */
  locked?: boolean;
  loading?: boolean;
};

export function EdgePill({ edgePts, home, away, threshold, locked, loading }: EdgePillProps) {
  if (loading) {
    return <span aria-hidden className="block h-6 w-19 shrink-0 rounded-full bg-secondary" />;
  }

  const text = formatEdge(edgePts, home, away);

  if (edgePts === null) {
    return <Badge variant="quiet" title="No line">{text}</Badge>;
  }
  if (locked) {
    return (
      <Badge variant="locked">
        <Lock aria-hidden />
        {text}
      </Badge>
    );
  }
  // The raw edge against the threshold, as the pick rule does: 2.46 prints +2.5 but is no pick.
  return <Badge variant={Math.abs(edgePts) >= threshold ? "edge" : "quiet"}>{text}</Badge>;
}
