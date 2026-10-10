import type { Metadata } from "next";

import { signIn } from "@/auth";
import { continuePath, loginState, safeNextPath } from "@/lib/login";

import { DeniedNotice, LoginCard, SignInButton, UnavailableNote } from "./login-card";

export const metadata: Metadata = { title: "Sign in · CFB Model" };

// The card depends on the URL, so it renders per request; nothing here is worth a static shell.
export const instant = false;

// S-15 (TASK-002, F-42 items 1 and 3). The proxy sends a signed-out visit here with Auth.js's
// callbackUrl; a refused GitHub account comes back with ?error=AccessDenied&login=<login>.
export default async function Login({ searchParams }: PageProps<"/login">) {
  const params = await searchParams;
  // Previews have no GitHub client (D-102): say so instead of drawing a button that can't work.
  const state = loginState(params, !!process.env.AUTH_GITHUB_ID);
  const redirectTo = continuePath(safeNextPath(params.callbackUrl));

  async function signInWithGitHub() {
    "use server";
    await signIn("github", { redirectTo });
  }

  // GitHub shows its account picker instead of reusing the account it is signed in as.
  async function useOtherAccount() {
    "use server";
    await signIn("github", { redirectTo }, { prompt: "select_account" });
  }

  switch (state.kind) {
    case "unavailable":
      return (
        <LoginCard footnote={false}>
          <UnavailableNote />
        </LoginCard>
      );
    case "denied":
      return (
        <LoginCard>
          <DeniedNotice login={state.login} useOtherAccount={useOtherAccount} />
        </LoginCard>
      );
    case "default":
      return (
        <LoginCard>
          <SignInButton action={signInWithGitHub} />
        </LoginCard>
      );
  }
}
