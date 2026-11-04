import { cn } from "@/lib/utils";

// The line-movement sparkline (Market Extras.dc.html › Line-movement cell): 22×10, one point per
// value, spread evenly left to right. Values are a line from one team's side, more favoured is
// more negative, and the most favoured sits at the top. All equal draws a flat line at mid-height.
// Decorative: the opener and the current line beside it say the same thing in numbers.

const WIDTH = 22;
const HEIGHT = 10;
/** Room for the stroke at the top and bottom. */
const INSET = 1;

/** The polyline's points, rounded to one decimal as the board draws them. */
export function sparklinePoints(values: number[], width = WIDTH, height = HEIGHT): string {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const range = hi - lo;
  const last = Math.max(values.length - 1, 1);
  return values
    .map((v, i) => {
      const x = (i / last) * width;
      const y = range ? INSET + ((v - lo) / range) * (height - 2 * INSET) : height / 2;
      return `${Number(x.toFixed(1))},${Number(y.toFixed(1))}`;
    })
    .join(" ");
}

export function Sparkline({ values, className }: { values: number[]; className?: string }) {
  return (
    <svg
      aria-hidden="true"
      width={WIDTH}
      height={HEIGHT}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className={cn("shrink-0 overflow-visible", className)}
    >
      <polyline
        points={sparklinePoints(values)}
        className="fill-none stroke-muted-foreground"
        strokeWidth={1.25}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
