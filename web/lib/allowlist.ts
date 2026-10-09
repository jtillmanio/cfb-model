// The one GitHub account allowed in (D-012). `allowed` is AUTH_ALLOWED_GITHUB_ID: the numeric
// user ID, not the username, because usernames can be renamed. Unset or blank refuses everyone.
export function isAllowedGitHubId(id: unknown, allowed: string | undefined): boolean {
  const allowedId = allowed?.trim();
  if (!allowedId) return false;
  if (typeof id !== "string" && typeof id !== "number") return false;
  return String(id) === allowedId;
}
