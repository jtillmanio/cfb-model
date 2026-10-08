import { redirect } from "next/navigation";

// The walking skeleton has one screen. This Week takes over `/` in Phase 4.
export default function Home() {
  redirect("/teams");
}
