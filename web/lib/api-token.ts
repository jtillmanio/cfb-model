import "server-only";

import { SignJWT } from "jose";

// The token Next's server code sends with every API call except health (02 › Auth, D-105).
// FastAPI verifies it with the same secret and checks the issuer and audience (TASK-004).
export const API_TOKEN_ISSUER = "cfb-model-web";
export const API_TOKEN_AUDIENCE = "cfb-model-api";

// Minted per request and sent at once, so a minute covers the call; anything longer only widens
// the window in which a leaked token could be replayed.
export const API_TOKEN_TTL_SECONDS = 60;

// HS256 is only as strong as its key: at least 256 bits (RFC 7518 § 3.2), here 32 characters.
const MIN_SECRET_LENGTH = 32;

function signingKey(): Uint8Array {
  const secret = process.env.API_JWT_SECRET;
  // Never put the value in the message: errors reach logs.
  if (!secret) throw new Error("API_JWT_SECRET is not set; the API can't be called.");
  if (secret.length < MIN_SECRET_LENGTH) {
    throw new Error(`API_JWT_SECRET is shorter than ${MIN_SECRET_LENGTH} characters.`);
  }
  return new TextEncoder().encode(secret);
}

// `sub` is the session's GitHub user ID (auth.config.ts stores it in the session as user.id).
export async function mintApiToken(githubId: string): Promise<string> {
  if (!githubId) throw new Error("An API token needs the signed-in GitHub user ID.");
  const key = signingKey();
  const now = Math.floor(Date.now() / 1000);
  return new SignJWT()
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setSubject(githubId)
    .setIssuer(API_TOKEN_ISSUER)
    .setAudience(API_TOKEN_AUDIENCE)
    .setIssuedAt(now)
    .setExpirationTime(now + API_TOKEN_TTL_SECONDS)
    .sign(key);
}
