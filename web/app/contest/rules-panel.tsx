import { type ContestRules, rulesRows, rulesSentence } from "@/lib/contest";

// The contest's rules, read-only (S-02, TASK-073; Contest Desktop's Rules tab). The form that
// edits them is M8.8, so there is no preset picker and no Save here. Desktop only: the tab is
// hidden below 1024 (contest-tabs.tsx).

export function RulesPanel({ name, rules }: { name: string; rules: ContestRules }) {
  return (
    <div data-slot="rules-panel" className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
      <dl className="rounded-lg border bg-card">
        <div className="flex min-h-11 items-center gap-4 border-b px-4 py-2 text-body">
          <dt className="w-40 shrink-0 text-muted-foreground">Contest</dt>
          <dd className="font-medium">{name}</dd>
        </div>
        {rulesRows(rules).map(([label, value]) => (
          <div key={label} className="flex min-h-11 items-center gap-4 border-b px-4 py-2 text-body last:border-b-0">
            <dt className="w-40 shrink-0 text-muted-foreground">{label}</dt>
            <dd className="font-medium">{value}</dd>
          </div>
        ))}
      </dl>
      <section className="flex flex-col gap-1 rounded-lg border bg-card p-4">
        <h2 className="text-panel font-semibold">This week, in plain English</h2>
        <p className="text-body text-muted-foreground">{rulesSentence(rules)}</p>
      </section>
    </div>
  );
}
