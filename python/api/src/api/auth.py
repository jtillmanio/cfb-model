"""The JWT check on every API route except health (docs/02 › Auth, D-012, D-105).

Next's server code mints the token in web/lib/api-token.ts; the claims, algorithm and secret
floor here must match it. On Vercel /api/py/* reaches FastAPI directly (D-100), so this check is
the API's only gate.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ISSUER = "cfb-model-web"
AUDIENCE = "cfb-model-api"

# HS256 only: naming the one algorithm refuses `none` and every other `alg` a token claims.
ALGORITHMS = ["HS256"]

# The same floor web/lib/api-token.ts enforces: 256 bits of key (RFC 7518 § 3.2).
MIN_SECRET_LENGTH = 32

# Next and the API run as separate functions whose clocks can drift by a second or two.
LEEWAY_SECONDS = 5

log = logging.getLogger(__name__)

# auto_error=False so a missing header gets the same refusal as a bad token.
bearer = HTTPBearer(auto_error=False)


def _refuse() -> HTTPException:
    # One fixed message for every case: never echo the token, the secret or why it failed.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_api_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    """Return the token's `sub` (the GitHub user ID), or refuse with 401."""
    # Read per request, so a missing or short secret fails closed rather than at import.
    secret = os.environ.get("API_JWT_SECRET", "")
    if len(secret) < MIN_SECRET_LENGTH:
        # Name the variable, never its value: logs leave the function.
        log.error("API_JWT_SECRET is unset or shorter than %d characters", MIN_SECRET_LENGTH)
        raise _refuse()
    if credentials is None:
        raise _refuse()
    try:
        claims = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=ALGORITHMS,
            audience=AUDIENCE,
            issuer=ISSUER,
            leeway=LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.InvalidTokenError:
        raise _refuse() from None
    subject = claims["sub"]
    if not isinstance(subject, str) or not subject:
        raise _refuse()
    return subject
