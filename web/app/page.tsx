import { redirect } from "next/navigation";

// The walking skeleton has one screen. This Week takes over `/` in Phase 4.

// A redirect has no shell to validate: without this, `next dev` logs "Could not validate `instant`"
// on every visit (web/lib/redirect-pages-opt-out.test.ts).
export const instant = false;

export default function Home() {
  redirect("/teams");
}
