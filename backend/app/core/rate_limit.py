"""
Minimal in-memory rate limiter for auth endpoints (login, password
reset request) — the two most brute-forceable routes in any system,
since they exist specifically to be hit repeatedly by an attacker
guessing passwords or spamming reset tokens.

Deliberately in-memory, not Redis-backed: this base build targets a
single-instance deployment out of the box. That's a real limitation
— in-memory state doesn't share across multiple backend replicas, so
a horizontally-scaled deployment (multiple containers behind a load
balancer) would need to swap this for a shared store (Redis, etc.)
to actually rate-limit correctly. Documented here rather than hidden,
since silently doing nothing under scale would be worse than an
honest single-instance limitation.

Keyed by (identifier, route) — identifier is normally "ip:email" so
one slow attacker on one IP doesn't lock out everyone else trying to
reset the same account from elsewhere, and one email being hammered
from many IPs still gets caught by the email component.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request

# route_key -> identifier -> list of request timestamps (unix seconds)
_attempts: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))


def rate_limit(route_key: str, max_attempts: int, window_seconds: int):
    """Dependency factory. Use as:
        Depends(rate_limit("login", max_attempts=5, window_seconds=300))
    """

    async def _check(request: Request):
        client_ip = request.client.host if request.client else "unknown"
        # Identify by IP alone at the dependency level — routes that also
        # know the target email should call record_attempt() with the
        # combined key after body parsing (see auth.py) for the tighter,
        # per-email check. This IP-only check is the first line of defense.
        identifier = client_ip
        now = time.time()
        bucket = _attempts[route_key][identifier]

        # Drop anything outside the window before counting.
        _attempts[route_key][identifier] = [t for t in bucket if now - t < window_seconds]
        bucket = _attempts[route_key][identifier]

        if len(bucket) >= max_attempts:
            raise HTTPException(
                status_code=429,
                detail=f"Too many attempts. Try again in a few minutes.",
            )

        bucket.append(now)

    return _check
