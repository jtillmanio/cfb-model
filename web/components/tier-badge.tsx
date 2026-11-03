import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils";

// TierBadge (design/README.md › Components; D-063): one violet hue in three lightness steps, and
// the letter is always printed, so colour is never the only signal. C gets a 1px outline because
// its fill sits close to the card.

export type Tier = "A" | "B" | "C";

const tierVariants = cva(
  "inline-flex size-5 shrink-0 items-center justify-center rounded-sm text-caption font-bold",
  {
    variants: {
      tier: {
        A: "bg-tier-a text-tier-a-foreground",
        B: "bg-tier-b text-tier-b-foreground",
        C: "bg-tier-c text-tier-c-foreground ring-1 ring-inset ring-tier-b",
      },
    },
  },
);

type TierBadgeProps = {
  /** null when the game is not a pick. */
  tier: Tier | null;
  /** Adds the words ("Tier A") after the letter. */
  label?: boolean;
  loading?: boolean;
};

export function TierBadge({ tier, label, loading }: TierBadgeProps) {
  if (loading) {
    return <span aria-hidden className="block size-5 shrink-0 rounded-sm bg-secondary" />;
  }
  if (tier === null) {
    return (
      <span title="No pick" className="inline-flex w-5 justify-center text-muted-foreground">
        —
      </span>
    );
  }

  const badge = <span className={cn(tierVariants({ tier }))}>{tier}</span>;
  if (!label) return badge;
  return (
    <span className="inline-flex items-center gap-1.5">
      {badge}
      <span className="text-label font-medium">Tier {tier}</span>
    </span>
  );
}
