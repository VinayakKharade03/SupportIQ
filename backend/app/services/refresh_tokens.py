import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken
from app.services.security import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token

REFRESH_TOKEN_EXPIRE_DAYS = 30
CLEANUP_AFTER_DAYS = 7  # a user's rows expired for longer than this are deleted at login


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _invalid() -> HTTPException:
    return HTTPException(status_code=401, detail="Invalid or expired refresh token")


def _new_token(db: Session, user_id: int, family_id: str) -> str:
    raw = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=_hash(raw),
            family_id=family_id,
            expires_at=_now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return raw


def _pair(user_id: int, refresh_token: str) -> dict:
    return {
        "access_token": create_access_token({"sub": str(user_id)}),
        "token_type": "bearer",
        "refresh_token": refresh_token,
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def _revoke_family(db: Session, family_id: str) -> None:
    db.query(RefreshToken).filter(
        RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
    ).update({"revoked_at": _now()}, synchronize_session=False)


def create_token_pair(db: Session, user_id: int) -> dict:
    """Start a new login session: a fresh access token and refresh token."""
    cutoff = _now() - timedelta(days=CLEANUP_AFTER_DAYS)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id, RefreshToken.expires_at < cutoff
    ).delete(synchronize_session=False)
    raw = _new_token(db, user_id, str(uuid.uuid4()))
    db.commit()
    return _pair(user_id, raw)


def rotate(db: Session, raw_token: str) -> dict:
    """Exchange a refresh token for a new pair. Each refresh token works once."""
    row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == _hash(raw_token))
        .with_for_update()
        .first()
    )
    if row is None:
        raise _invalid()
    if row.revoked_at is not None:
        # An already-used token came back: treat it as stolen and end the whole session
        _revoke_family(db, row.family_id)
        db.commit()
        raise _invalid()
    if row.expires_at <= _now():
        raise _invalid()
    row.revoked_at = _now()
    new_raw = _new_token(db, row.user_id, row.family_id)
    db.commit()
    return _pair(row.user_id, new_raw)


def revoke_session(db: Session, raw_token: str) -> None:
    """Log out: end the session this refresh token belongs to. Unknown tokens are ignored."""
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == _hash(raw_token)).first()
    if row is not None:
        _revoke_family(db, row.family_id)
        db.commit()
