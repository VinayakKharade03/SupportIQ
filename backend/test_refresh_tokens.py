import hashlib
import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.security import decode_access_token

c = TestClient(app)
EMAIL = "zz_refresh_test@example.com"
PW = "refresh-test-pass-1"


def rows(uid):
    db = SessionLocal()
    try:
        return db.query(RefreshToken).filter(RefreshToken.user_id == uid).order_by(RefreshToken.id).all()
    finally:
        db.close()


def login():
    return c.post("/auth/login", json={"email": EMAIL, "password": PW})


def refresh(tok):
    return c.post("/auth/refresh", json={"refresh_token": tok})


def logout(tok):
    return c.post("/auth/logout", json={"refresh_token": tok})


def cart(access):
    return c.get("/orders/cart", headers={"Authorization": f"Bearer {access}"}).status_code


def remove_test_user():
    db = SessionLocal()
    u = db.query(User).filter(User.email == EMAIL).first()
    if u:
        db.delete(u)
        db.commit()
    db.close()


remove_test_user()
uid = None
try:
    r = c.post("/auth/signup", json={"email": EMAIL, "password": PW, "full_name": "Refresh Test"})
    uid = r.json()["id"]
    print("signup:", r.status_code, "(expect 200)")

    r = c.post("/auth/login", json={"email": EMAIL, "password": "wrong-password"})
    print("wrong password:", r.status_code, len(rows(uid)), "(expect 401 0)")

    r = login()
    body = r.json()
    a1, r1 = body.get("access_token"), body.get("refresh_token")
    print("login:", r.status_code, body.get("token_type"), body.get("expires_in"), bool(a1), bool(r1), "(expect 200 bearer 1800 True True)")
    left = decode_access_token(a1)["exp"] - time.time()
    print("access lifetime about 30 min:", 1700 < left <= 1805, "(expect True)")
    print("access token works on existing route:", cart(a1), "(expect 200)")
    stored = rows(uid)
    print("stored hashed:", len(stored) == 1, stored[0].token_hash == hashlib.sha256(r1.encode()).hexdigest(), stored[0].token_hash != r1, "(expect True True True)")

    r = refresh(r1)
    b2 = r.json()
    a2, r2 = b2.get("access_token"), b2.get("refresh_token")
    print("refresh:", r.status_code, bool(a2), r2 != r1, cart(a2), "(expect 200 True True 200)")
    stored = rows(uid)
    print("rotation:", len(stored) == 2, stored[0].revoked_at is not None, stored[1].revoked_at is None, stored[0].family_id == stored[1].family_id, "(expect True True True True)")

    print("reuse of old token:", refresh(r1).status_code, "(expect 401)")
    print("whole session revoked:", all(s.revoked_at is not None for s in rows(uid)), "(expect True)")
    print("newest token also dead:", refresh(r2).status_code, "(expect 401)")

    s2 = login().json()
    s3 = refresh(s2["refresh_token"]).json()
    print("logout:", logout(s3["refresh_token"]).status_code, "(expect 200)")
    print("refresh after logout:", refresh(s3["refresh_token"]).status_code, "(expect 401)")
    print("logout with garbage:", logout("not-a-real-token").status_code, "(expect 200)")
    print("unknown token:", refresh("not-a-real-token").status_code, "(expect 401)")
    print("tampered token:", refresh(s2["refresh_token"] + "x").status_code, "(expect 401)")
    print("empty token:", refresh("").status_code, "(expect 422)")

    sa, sb = login().json(), login().json()
    ra = refresh(sa["refresh_token"]).json()
    print("reuse in session A:", refresh(sa["refresh_token"]).status_code, "(expect 401)")
    print("session A dead:", refresh(ra["refresh_token"]).status_code, "(expect 401)")
    print("session B unaffected:", refresh(sb["refresh_token"]).status_code, "(expect 200)")

    se = login().json()
    db = SessionLocal()
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == hashlib.sha256(se["refresh_token"].encode()).hexdigest()).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    db.close()
    print("expired token:", refresh(se["refresh_token"]).status_code, "(expect 401)")
finally:
    remove_test_user()

db = SessionLocal()
left_users = db.query(User).filter(User.email == EMAIL).count()
left_tokens = db.query(RefreshToken).filter(RefreshToken.user_id == uid).count() if uid else 0
print("cleanup:", left_users == 0, left_tokens == 0, "(expect True True)")
db.close()
