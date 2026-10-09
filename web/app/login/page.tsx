import type { Metadata } from "next";

import { signIn } from "@/auth";

export const metadata: Metadata = { title: "Sign in · CFB Model" };

// S-15, minimal cut (TASK-001): the one action. The designed layout, the denied-account copy,
// the waking state and the preview note are TASK-002.
export default function Login() {
  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-6">
      <div className="flex w-full max-w-[360px] flex-col gap-6 rounded-lg border bg-card p-6">
        <h1 className="text-section font-semibold">CFB Model</h1>
        <form
          action={async () => {
            "use server";
            await signIn("github", { redirectTo: "/" });
          }}
        >
          <button
            type="submit"
            className="h-11 w-full rounded-md bg-primary px-4 font-medium text-primary-foreground hover:opacity-90"
          >
            Sign in with GitHub
          </button>
        </form>
      </div>
    </main>
  );
}
