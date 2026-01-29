from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt


@dataclass(frozen=True)
class AuthenticatedUser:
    """Authenticated user extracted from Supabase JWT."""

    sub: str
    email: Optional[str] = None
    raw_claims: Dict[str, Any] | None = None


_bearer = HTTPBearer(auto_error=False)
_jwks_cache: Dict[str, Any] | None = None


async def _get_jwks() -> Dict[str, Any]:
    """Fetch and cache JWKS from Supabase."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    jwks_url = os.getenv("SUPABASE_JWKS_URL")
    if not jwks_url:
        raise RuntimeError("SUPABASE_JWKS_URL env var is required for RS256 verification.")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


def _select_jwk(jwks: Dict[str, Any], kid: str) -> Dict[str, Any]:
    """Select a JWK by key id."""
    for k in jwks.get("keys", []):
        if k.get("kid") == kid:
            return k
    raise KeyError(f"kid={kid} not found in JWKS")


# PUBLIC_INTERFACE
async def get_current_user(
    creds: HTTPAuthorizationCredentials = Security(_bearer),
) -> AuthenticatedUser:
    """
    FastAPI dependency that verifies a Supabase JWT.

    Supported modes:
    - HS256: set SUPABASE_JWT_SECRET and optionally SUPABASE_JWT_AUDIENCE
    - RS256 (recommended): set SUPABASE_JWKS_URL and SUPABASE_JWT_AUDIENCE

    The user id is taken from the `sub` claim.
    """
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = creds.credentials
    audience = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")

    try:
        # Try RS256 first if JWKS configured
        jwks_url = os.getenv("SUPABASE_JWKS_URL")
        if jwks_url:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if not kid:
                raise HTTPException(status_code=401, detail="JWT header missing kid")

            jwks = await _get_jwks()
            jwk = _select_jwk(jwks, kid)
            key = json.dumps(jwk)
            claims = jwt.decode(token, key, algorithms=["RS256"], audience=audience, options={"verify_at_hash": False})
        else:
            # HS256 secret mode
            secret = os.getenv("SUPABASE_JWT_SECRET")
            if not secret:
                raise RuntimeError("Auth not configured. Provide SUPABASE_JWKS_URL or SUPABASE_JWT_SECRET.")
            claims = jwt.decode(token, secret, algorithms=["HS256"], audience=audience, options={"verify_at_hash": False})

        sub = claims.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="JWT missing sub claim")

        return AuthenticatedUser(sub=sub, email=claims.get("email"), raw_claims=claims)
    except (JWTError, KeyError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e
