"""Origin checks for localhost-only browser mutation endpoints."""

from __future__ import annotations

from urllib.parse import urlparse

LOCAL_HOSTS = {"127.0.0.1", "localhost"}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def is_trusted_local_request(
    *,
    method: str,
    origin: str | None,
    referer: str | None,
    sec_fetch_site: str | None,
    allowed_ports: set[int],
) -> bool:
    """Return whether a browser request may mutate local app state."""
    if method.upper() not in UNSAFE_METHODS:
        return True

    fetch_site = (sec_fetch_site or "").lower()
    if fetch_site == "cross-site":
        return False

    if origin:
        return _is_allowed_local_url(origin, allowed_ports)

    if referer:
        return _is_allowed_local_url(referer, allowed_ports)

    if fetch_site == "same-site":
        return False

    # Non-browser local clients often omit Origin/Referer. Keep those working.
    return True


def _is_allowed_local_url(value: str, allowed_ports: set[int]) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https", "tauri"}:
        return False
    host = (parsed.hostname or "").lower()
    if host not in LOCAL_HOSTS:
        return False
    if parsed.scheme == "tauri":
        return True
    return parsed.port in allowed_ports
