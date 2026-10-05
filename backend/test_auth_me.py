from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.user import User
from app.services.security import create_access_token

c = TestClient(app)
db = SessionLocal()


def hdr(email):
    uid = db.query(User).filter(User.email == email).one().id
    return {"Authorization": f"Bearer {create_access_token({'sub': str(uid)})}"}


print("no token:", c.get("/auth/me").status_code, "(expect 401)")
print("bad token:", c.get("/auth/me", headers={"Authorization": "Bearer not-a-token"}).status_code, "(expect 401)")

r = c.get("/auth/me", headers=hdr("user@example.com"))
b = r.json()
print("normal user:", r.status_code, b.get("email"), b.get("is_admin"), "(expect 200 user@example.com False)")
r = c.get("/auth/me", headers=hdr("admin@gmail.com"))
b = r.json()
print("admin:", r.status_code, b.get("email"), b.get("is_admin"), "(expect 200 admin@gmail.com True)")
print("fields:", sorted(b.keys()), "(expect id, email, full_name, created_at, is_admin only)")
print("no password data:", not any("password" in k for k in b), "(expect True)")
db.close()
