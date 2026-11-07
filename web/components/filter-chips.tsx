"use client";

import { Check } from "lucide-react";
import { type ReactNode, useState } from "react";

import { Toggle } from "./ui/toggle";

// Filter chips (design/README.md › Forms & controls): selected = ink fill + check. Each chip is a
// real <button aria-pressed>, so Enter and Space toggle it. Controlled (`selected`) or
// uncontrolled (`defaultSelected`); both report the new selection through `onChange`.

export type ChipOption = { value: string; label: ReactNode };

type FilterChipsProps = {
  options: ChipOption[];
  selected?: string[];
  defaultSelected?: string[];
  onChange?: (selected: string[]) => void;
  /** Names the group for screen readers. */
  label?: string;
};

export function FilterChips({
  options,
  selected,
  defaultSelected = [],
  onChange,
  label,
}: FilterChipsProps) {
  const [internal, setInternal] = useState(defaultSelected);
  const current = selected ?? internal;

  function toggle(value: string) {
    const next = current.includes(value)
      ? current.filter((entry) => entry !== value)
      : [...current, value];
    if (selected === undefined) setInternal(next);
    onChange?.(next);
  }

  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((option) => {
        const pressed = current.includes(option.value);
        return (
          <Toggle
            key={option.value}
            variant="chip"
            pressed={pressed}
            onPressedChange={() => toggle(option.value)}
          >
            {pressed ? <Check aria-hidden className="size-3.5" /> : null}
            {option.label}
          </Toggle>
        );
      })}
    </div>
  );
}
