import type { NextAuthConfig } from "next-auth";
import GitHub from "next-auth/providers/github";

import { isAllowedGitHubId } from "@/lib/allowlist";
import { deniedLoginUrl } from "@/lib/login";
import { previewUserId } from "@/lib/preview";

// A session lasts 90 days on a device (D-095).
export const SESSION_MAX_AGE_SECONDS = 90 * 24 * 60 * 60;

// GitHub reads AUTH_GITHUB_ID and AUTH_GITHUB_SECRET; the cookie is signed with AUTH_SECRET.
// Previews set no GitHub client (D-153): the config still loads, and `authorized` lets every
// request in as the allowlisted user, behind Vercel Authentication.
export const authConfig = {
  providers: [GitHub],
  session: { strategy: "jwt", maxAge: SESSION_MAX_AGE_SECONDS },
  // Other sign-in errors land on /login?error=<type>.
  pages: { signIn: "/login", error: "/login" },
  callbacks: {
    // A refused GitHub account goes to /login with its GitHub login, so the page can say who was
    // refused (TASK-002). Auth.js redirects to a returned string instead of raising AccessDenied.
    signIn({ account, profile }) {
      if (account?.provider !== "github") return false;
      if (isAllowedGitHubId(profile?.id, process.env.AUTH_ALLOWED_GITHUB_ID)) return true;
      const login = typeof profile?.login === "string" ? profile.login : undefined;
      return deniedLoginUrl(login);
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
    // AUTH_ALLOWED_GITHUB_ID locks out existing sessions without rotating AUTH_SECRET. A Vercel
    // preview lets every request through as the allowlisted user (D-153): Vercel's login already
    // decided who reached it.
    authorized({ auth }) {
      if (previewUserId()) return true;
      return isAllowedGitHubId(auth?.user?.id, process.env.AUTH_ALLOWED_GITHUB_ID);
    },
  },
} satisfies NextAuthConfig;
