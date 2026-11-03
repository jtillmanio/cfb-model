import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// The design type scale (`text-caption` … `text-title`, globals.css @theme) are font sizes.
// tailwind-merge only knows the default sizes and would read `text-caption` as a colour, so
// `cn("text-caption", "text-muted-foreground")` would drop the size.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [
        { text: ["caption", "label", "body", "panel", "section", "title"] },
      ],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
