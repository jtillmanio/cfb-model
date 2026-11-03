import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { EdgePill } from "@/components/edge-pill";
import { FilterChips } from "@/components/filter-chips";
import { ResultMarker } from "@/components/result-marker";
import { TierBadge } from "@/components/tier-badge";

// Design-system specimen page (D-152): every drawn state of the shared components, once in a dark
// panel and once in a light one (tokens.css scopes each theme by class), against static sample
// props. No API call. It is the owner's review surface for M5.2; production does not ship it.

export const metadata: Metadata = { title: "Design system · CFB Model" };

// Sample data only: the real pick threshold comes from the active version's spec (D-055).
const SAMPLE_THRESHOLD = 2.5;

const CHIP_OPTIONS = [
  { value: "all", label: "All" },
  { value: "picks", label: "Picks only" },
  { value: "fbs", label: "FBS vs FBS" },
  { value: "ranked", label: "Ranked" },
];

function Specimen({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <figure className="m-0 flex min-w-0 flex-col items-start gap-2">
      <figcaption className="text-caption text-muted-foreground">{caption}</figcaption>
      {children}
    </figure>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex min-w-0 flex-col gap-4 rounded-lg border bg-card p-4">
      <h3 className="text-panel font-semibold">{title}</h3>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">{children}</div>
    </section>
  );
}

function Specimens({ theme }: { theme: "dark" | "light" }) {
  const id = `${theme}-heading`;
  return (
    <section
      aria-labelledby={id}
      data-theme-panel={theme}
      className={`${theme} flex min-w-0 flex-col gap-4 rounded-xl border bg-background p-4 text-foreground`}
    >
      <h2 id={id} className="text-section font-semibold">
        {theme === "dark" ? "Dark" : "Light"}
      </h2>

      <Group title="Edge pill">
        <Specimen caption="Clears 2.5 · pick">
          <EdgePill edgePts={3.7} home="OSU" away="UTAH" threshold={SAMPLE_THRESHOLD} />
        </Specimen>
        <Specimen caption="Below threshold">
          <EdgePill edgePts={-0.6} home="OSU" away="UTAH" threshold={SAMPLE_THRESHOLD} />
        </Specimen>
        <Specimen caption="Exactly 2.5">
          <EdgePill edgePts={2.5} home="OSU" away="UTAH" threshold={SAMPLE_THRESHOLD} />
        </Specimen>
        <Specimen caption="No line">
          <EdgePill edgePts={null} home="OSU" away="UTAH" threshold={SAMPLE_THRESHOLD} />
        </Specimen>
        <Specimen caption="Locked">
          <EdgePill edgePts={0.9} home="UNLV" away="BSU" threshold={SAMPLE_THRESHOLD} locked />
        </Specimen>
        <Specimen caption="Loading">
          <EdgePill edgePts={3.7} home="OSU" away="UTAH" threshold={SAMPLE_THRESHOLD} loading />
        </Specimen>
      </Group>

      <Group title="Tier badge">
        <Specimen caption="A · edge ≥ 5.0">
          <TierBadge tier="A" />
        </Specimen>
        <Specimen caption="B · ≥ 3.5">
          <TierBadge tier="B" />
        </Specimen>
        <Specimen caption="C · ≥ 2.5">
          <TierBadge tier="C" />
        </Specimen>
        <Specimen caption="No pick">
          <TierBadge tier={null} />
        </Specimen>
        <Specimen caption="Labelled">
          <TierBadge tier="A" label />
        </Specimen>
        <Specimen caption="Loading">
          <TierBadge tier="A" loading />
        </Specimen>
      </Group>

      <Group title="Result marker">
        <Specimen caption="Covered">
          <ResultMarker result="covered" showLabel />
        </Specimen>
        <Specimen caption="Not covered">
          <ResultMarker result="not_covered" showLabel />
        </Specimen>
        <Specimen caption="Push">
          <ResultMarker result="push" showLabel />
        </Specimen>
        <Specimen caption="Pending">
          <ResultMarker result="pending" />
        </Specimen>
        <Specimen caption="Compact">
          <span className="flex items-center gap-1">
            <ResultMarker result="covered" />
            <ResultMarker result="not_covered" />
            <ResultMarker result="push" />
          </span>
        </Specimen>
      </Group>

      <Group title="Filter chips">
        <div className="col-span-full flex min-w-0 flex-col gap-2">
          <p className="text-caption text-muted-foreground">
            “Picks only” selected. Click, or Tab to a chip and press Enter or Space.
          </p>
          <FilterChips label={`${theme} filters`} options={CHIP_OPTIONS} defaultSelected={["picks"]} />
        </div>
      </Group>
    </section>
  );
}

export default function DesignSystem() {
  // Previews and the fixture build show the page; the owner's production app does not ship it.
  if (process.env.VERCEL_ENV === "production") notFound();

  return (
    <main className="mx-auto w-full max-w-[1216px] px-4 py-6 md:px-6 xl:px-8">
      <header className="mb-6 flex flex-col gap-1">
        <h1 className="text-section font-semibold md:text-title">Design system</h1>
        <p className="text-caption text-muted-foreground md:text-body">
          Badges and chips, every drawn state, dark and light
        </p>
      </header>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Specimens theme="dark" />
        <Specimens theme="light" />
      </div>
    </main>
  );
}
