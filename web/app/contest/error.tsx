"use client";

import { ApiUnreachable } from "@/components/shell/api-unreachable";

// A fallback for anything page.tsx doesn't catch itself. page.tsx draws "API unreachable" inside
// the shell when its one API call fails (D-096); this boundary only sees an unexpected error, and
// it draws no shell, so the shell's code never ships to the browser (D-157). The page's own markup
// is repeated here, not imported, so the paste flow stays out of this bundle.
export default function ContestError({ retry }: { error: unknown; retry: () => void }) {
  return (
    <main className="mx-auto w-full max-w-304 px-4 py-6 md:px-6">
      <header className="mb-4">
        <h1 className="text-section font-semibold tracking-[-0.005em] md:text-title">Contest</h1>
      </header>
      <ApiUnreachable request="GET /api/py/contest" retry={retry} />
    </main>
  );
}
