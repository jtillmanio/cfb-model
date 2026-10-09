// Every page needs the allowlisted session (D-012). Auth.js runs the `authorized` callback in
// auth.config.ts: no session, a garbage, wrongly signed or expired cookie, or another GitHub ID
// gets a redirect to /login, never a 500. A valid session's cookie is re-issued for 90 more days.
export { auth as proxy } from "@/auth";

export const config = {
  // Open without a session: the login page, Auth.js's own routes, the API (on Vercel /api/py/*
  // never reaches Next, D-100; locally it is a rewrite, and the API checks its own JWT), Next's
  // assets, and files such as favicon.ico.
  matcher: ["/((?!login$|api/auth/|api/py/|_next/|.*\\.\\w+$).*)"],
};
