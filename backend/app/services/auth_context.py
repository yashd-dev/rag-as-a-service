from dataclasses import dataclass

from flask import current_app, request


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    organization_id: str
    role: str | None


class AuthError(Exception):
    pass


def current_auth_context() -> AuthContext:
    expected_secret = current_app.config.get("BACKEND_INTERNAL_SECRET")
    actual_secret = request.headers.get("X-Internal-Secret")
    if not expected_secret:
        raise AuthError("Trusted backend authentication is not configured")
    if actual_secret != expected_secret:
        raise AuthError("Invalid internal secret")

    user_id = request.headers.get("X-User-Id")
    organization_id = request.headers.get("X-Organization-Id")
    if not user_id or not organization_id:
        raise AuthError("Missing auth context")

    return AuthContext(
        user_id=user_id,
        organization_id=organization_id,
        role=request.headers.get("X-User-Role"),
    )
