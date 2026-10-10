import type { ReactNode } from "react";

import { LOGIN_COPY } from "@/lib/login";

// S-15 sign-in card (TASK-002), from App States Desktop / Mobile (frame "login") and Pass A
// A1a–f: wordmark over one card, footnote below. Phone: top-aligned, 16px gutter, 44px controls.
// From md up: centered, 380px card, 36px button. The card's body is one state at a time.

export function LoginCard({ footnote = true, children }: { footnote?: boolean; children: ReactNode }) {
  return (
    <main className="flex min-h-dvh flex-col gap-5 px-4 pt-24 pb-6 md:items-center md:justify-center md:p-10">
      <div className="flex items-center justify-center gap-2.5">
        <span
          aria-hidden
          className="flex size-7 shrink-0 items-center justify-center rounded-md bg-foreground font-mono text-caption leading-none font-bold text-background"
        >
          CF
        </span>
        <span className="text-panel font-semibold">{LOGIN_COPY.wordmark}</span>
      </div>
      <div className="flex w-full flex-col gap-4 rounded-lg border bg-card p-5 md:w-95 md:p-6">
        <div className="flex flex-col gap-0.5">
          <h1 className="text-section font-semibold">{LOGIN_COPY.heading}</h1>
          <p className="text-label text-muted-foreground">{LOGIN_COPY.subhead}</p>
        </div>
        {children}
      </div>
      {footnote && (
        <p className="text-center text-caption text-muted-foreground">{LOGIN_COPY.footnote}</p>
      )}
    </main>
  );
}

type Action = () => Promise<void>;

export function SignInButton({ action }: { action: Action }) {
  return (
    <form action={action}>
      <button
        type="submit"
        className="flex h-11 w-full items-center justify-center gap-2 rounded-md bg-primary px-4 text-body font-semibold text-primary-foreground hover:opacity-90 md:h-9"
      >
        <GitHubIcon />
        {LOGIN_COPY.signIn}
      </button>
    </form>
  );
}

export function DeniedNotice({ login, useOtherAccount }: { login: string | null; useOtherAccount: Action }) {
  return (
    <div
      role="alert"
      className="flex gap-2.5 rounded-md border border-destructive bg-destructive/8 p-3 md:px-3.5"
    >
      <AlertIcon />
      <div className="flex min-w-0 flex-col gap-1">
        <p className="text-body font-semibold">{LOGIN_COPY.deniedTitle}</p>
        <p className="text-label text-pretty">
          {login ? (
            <>
              You&apos;re signed in to GitHub as <b className="font-semibold">{login}</b>.{" "}
            </>
          ) : null}
          Only the one allowlisted account can use this app.
        </p>
        <form action={useOtherAccount}>
          <button
            type="submit"
            className="inline-flex min-h-11 items-center text-body font-medium underline underline-offset-2 md:min-h-6 md:text-label"
          >
            {LOGIN_COPY.useOther}
          </button>
        </form>
      </div>
    </div>
  );
}

export function WakingNotice() {
  return (
    <div role="status" className="flex flex-col gap-2">
      <p className="flex h-11 items-center justify-center gap-2 rounded-md bg-secondary text-body font-medium text-muted-foreground md:h-9">
        <SpinnerIcon />
        {LOGIN_COPY.wakingTitle}
      </p>
      <p className="text-center text-caption text-pretty text-muted-foreground">
        {LOGIN_COPY.wakingNote}
      </p>
    </div>
  );
}

// Not in the design (D-102): previews have no GitHub client, so there is nothing to press.
export function UnavailableNote() {
  return <p className="text-label text-muted-foreground">{LOGIN_COPY.unavailable}</p>;
}

// Lucide icons (the design's icon set), inlined: 24px grid, 2px stroke, drawn in currentColor.
function Icon({ className, children }: { className: string; children: ReactNode }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 ${className}`}
    >
      {children}
    </svg>
  );
}

function GitHubIcon() {
  return (
    <Icon className="size-4">
      <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
      <path d="M9 18c-4.51 2-5-2-7-2" />
    </Icon>
  );
}

function AlertIcon() {
  return (
    <Icon className="mt-0.5 size-4 text-destructive">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" x2="12" y1="8" y2="12" />
      <line x1="12" x2="12.01" y1="16" y2="16" />
    </Icon>
  );
}

// Spins only when the viewer allows motion (AC-5).
function SpinnerIcon() {
  return (
    <Icon className="size-3.5 motion-safe:animate-spin">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </Icon>
  );
}
