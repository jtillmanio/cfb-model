import type { NextAuthConfig } from "next-auth";
import GitHub from "next-auth/providers/github";

import { isAllowedGitHubId } from "@/lib/allowlist";

// A session lasts 90 days on a device (D-095).
export const SESSION_MAX_AGE_SECONDS = 90 * 24 * 60 * 60;

// GitHub reads AUTH_GITHUB_ID and AUTH_GITHUB_SECRET; the cookie is signed with AUTH_SECRET.
// Previews set no GitHub client (D-102): the config still loads, and only minted sessions get in.
export const authConfig = {
  providers: [GitHub],
  session: { strategy: "jwt", maxAge: SESSION_MAX_AGE_SECONDS },
  // A refused sign-in lands on /login?error=AccessDenied.
  pages: { signIn: "/login", error: "/login" },
  callbacks: {
    signIn({ account, profile }) {
      return (
        account?.provider === "github" &&
        isAllowedGitHubId(profile?.id, process.env.AUTH_ALLOWED_GITHUB_ID)
      );
    },
    // Without an adapter Auth.js makes `sub` a random UUID; store the GitHub ID instead, so
    // every request can be checked against the allowlist.
    jwt({ token, account, profile }) {
      if (account?.provider === "github" && profile?.id != null) {
        token.sub = String(profile.id);
      }
      return token;
    },
    session({ session, token }) {
      return { ...session, user: { ...session.user, id: token.sub ?? "" } };
    },
    // Runs in proxy.ts on every page request. Re-checking the allowlist means emptying or changing
    // AUTH_ALLOWED_GITHUB_ID locks out existing sessions without rotating AUTH_SECRET.
    authorized({ auth }) {
      return isAllowedGitHubId(auth?.user?.id, process.env.AUTH_ALLOWED_GITHUB_ID);
    },
  },
} satisfies NextAuthConfig;
