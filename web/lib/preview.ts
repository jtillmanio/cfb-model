// Previews trust Vercel Authentication (D-153, TASK-059). Deployment Protection lets only the
// owner's Vercel account open a preview, so on one the app treats every request as the allowlisted
// GitHub user, with no sign-in. VERCEL_ENV is set by Vercel and read per request: a request can't
// change it, and it is unset locally, in CI and in e2e unless a server sets it.
//
// The allowlisted ID on a Vercel preview; null anywhere else, or when AUTH_ALLOWED_GITHUB_ID is
// unset or blank (the gate then stays shut, as the allowlist check does).
export function previewUserId(): string | null {
  if (process.env.VERCEL_ENV !== "preview") return null;
  return process.env.AUTH_ALLOWED_GITHUB_ID?.trim() || null;
}
