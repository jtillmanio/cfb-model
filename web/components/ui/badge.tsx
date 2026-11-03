import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";

import { cn } from "@/lib/utils";

// shadcn's Badge, restyled to the design tokens (design/README.md › Components). Pills take no
// hover or focus of their own: the row or card is the single hit target.
const badgeVariants = cva(
  "inline-flex h-6 w-fit shrink-0 items-center justify-center gap-1 whitespace-nowrap rounded-full px-2 text-label [&>svg]:pointer-events-none [&>svg]:size-3",
  {
    variants: {
      variant: {
        // Filled `--edge`: the model clears the pick threshold.
        edge: "bg-edge font-semibold text-edge-foreground",
        // Plain text: a number that is shown but is not a pick.
        quiet: "text-muted-foreground",
        // A pill whose game has started: muted fill, locked tone.
        locked: "bg-muted font-medium text-locked",
        secondary: "bg-secondary text-secondary-foreground",
        outline: "border border-border text-foreground",
      },
    },
    defaultVariants: {
      variant: "secondary",
    },
  },
);

function Badge({
  className,
  variant,
  asChild = false,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "span";

  return (
    <Comp
      data-slot="badge"
      data-variant={variant ?? "secondary"}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  );
}

export { Badge, badgeVariants };
