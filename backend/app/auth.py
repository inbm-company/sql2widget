import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app import config
from app.db import execute, fetch_one

ph = PasswordHasher()
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: str, tenant_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "type": "access",
        "exp": _now() + timedelta(minutes=config.JWT_ACCESS_MINUTES),
    }
    return jwt.encode(payload, config.APP_SECRET, algorithm="HS256")


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_refresh_token(user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    token_id = f"rt_{secrets.token_hex(8)}"
    expires = _now() + timedelta(days=config.JWT_REFRESH_DAYS)
    execute(
        """
        INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at)
        VALUES (%s, %s, %s, %s)
        """,
        (token_id, user_id, hash_refresh_token(token), expires),
    )
    return token


def rotate_refresh_token(raw_token: str) -> tuple[dict, str, str]:
    token_hash = hash_refresh_token(raw_token)
    row = fetch_one(
        """
        SELECT rt.*, u.email, u.role, u.tenant_id
        FROM refresh_tokens rt
        JOIN users u ON u.id = rt.user_id
        WHERE rt.token_hash = %s
        """,
        (token_hash,),
    )
    if not row:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if row["revoked_at"] is not None:
        execute(
            "UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL",
            (row["user_id"],),
        )
        raise HTTPException(status_code=401, detail="Refresh token reuse detected")
    if row["expires_at"] < _now():
        raise HTTPException(status_code=401, detail="Refresh token expired")

    execute(
        "UPDATE refresh_tokens SET revoked_at = now() WHERE id = %s",
        (row["id"],),
    )
    new_refresh = issue_refresh_token(row["user_id"])
    access = create_access_token(row["user_id"], row["tenant_id"], row["role"])
    user = {
        "id": row["user_id"],
        "email": row["email"],
        "role": row["role"],
        "tenant_id": row["tenant_id"],
    }
    return user, access, new_refresh


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, config.APP_SECRET, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = fetch_one(
            "SELECT id, email, role, tenant_id FROM users WHERE id = %s",
            (payload["sub"],),
        )
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
