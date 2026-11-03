import { cn } from "@/lib/utils";

// ResultMarker (design/README.md › Components › Numbers & badges): glyph first, colour second,
// and a text label for screen readers, so colour is never the only signal.
// `showLabel` is the board's labelled variant; without it the label is for screen readers only.

export type ResultState = "covered" | "not_covered" | "push" | "pending";

const MARKERS = {
  covered: { glyph: "✓", label: "Covered", tone: "text-pos" },
  not_covered: { glyph: "✗", label: "Not covered", tone: "text-neg" },
  push: { glyph: "P", label: "Push", tone: "text-push" },
} as const;

export function ResultMarker({
  result,
  showLabel = false,
}: {
  result: ResultState;
  showLabel?: boolean;
}) {
  if (result === "pending") {
    return (
      <span className="inline-flex size-5 shrink-0 items-center justify-center rounded-sm border border-dashed border-input">
        <span className="sr-only">Pending</span>
      </span>
    );
  }

  const { glyph, label, tone } = MARKERS[result];
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-sm border border-current font-bold",
        showLabel ? "h-6 gap-1 px-2 text-label" : "size-5 text-caption",
        tone,
      )}
    >
      <span aria-hidden>{glyph}</span>
      <span className={showLabel ? "font-medium" : "sr-only"}>{label}</span>
    </span>
  );
}
