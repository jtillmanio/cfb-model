"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Toggle as TogglePrimitive } from "radix-ui";

import { cn } from "@/lib/utils";

// shadcn's Toggle, restyled to the design tokens. Radix renders a real <button> with
// aria-pressed and data-state="on" | "off".
const toggleVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap text-label font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "h-8 rounded-md px-3 hover:bg-accent data-[state=on]:bg-accent data-[state=on]:text-accent-foreground",
        // Filter chip: outlined; selected = ink fill (`--primary`) plus a check.
        // Desktop controls are h32; mobile pads the target to 44.
        chip: "h-8 rounded-full border border-input px-3 text-foreground hover:bg-accent data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-primary-foreground max-md:h-11",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

function Toggle({
  className,
  variant,
  ...props
}: React.ComponentProps<typeof TogglePrimitive.Root> & VariantProps<typeof toggleVariants>) {
  return (
    <TogglePrimitive.Root
      data-slot="toggle"
      className={cn(toggleVariants({ variant }), className)}
      {...props}
    />
  );
}

export { Toggle, toggleVariants };
