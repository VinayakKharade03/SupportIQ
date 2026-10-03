from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.user import User
from app.services.security import create_access_token

c = TestClient(app)


def user_id(email):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        if not u:
            raise SystemExit(f"User {email} not found")
        return u.id
    finally:
        db.close()


def auth(uid):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(uid)})}"}


user_id_normal = user_id("user@example.com")
admin_id = user_id("admin@gmail.com")
normal = auth(user_id_normal)
admin = auth(admin_id)

print("no token:", c.get("/admin/users").status_code, "(expect 401)")
print("normal user list:", c.get("/admin/users", headers=normal).status_code, "(expect 403)")

r = c.get("/admin/users", headers=admin)
rows = r.json()
print("admin list:", r.status_code, "count:", len(rows), "| has password field:", any("hashed_password" in x for x in rows), "(expect False)")
print("search admin:", len(c.get("/admin/users?search=admin", headers=admin).json()), "(expect 1)")
print("only admins:", len(c.get("/admin/users?is_admin=true", headers=admin).json()), "(expect 1)")
print("detail:", c.get(f"/admin/users/{user_id_normal}", headers=admin).json())
print("missing user:", c.get("/admin/users/99999", headers=admin).status_code, "(expect 404)")
print("bad body:", c.patch(f"/admin/users/{user_id_normal}/role", json={"is_admin": "maybe"}, headers=admin).status_code, "(expect 422)")
print("change own role:", c.patch(f"/admin/users/{admin_id}/role", json={"is_admin": False}, headers=admin).status_code, "(expect 400)")

try:
    r = c.patch(f"/admin/users/{user_id_normal}/role", json={"is_admin": True}, headers=admin)
    print("promote:", r.status_code, r.json()["is_admin"], "(expect 200 True)")
    print("promoted user can list now:", c.get("/admin/users", headers=normal).status_code, "(expect 200)")
finally:
    r = c.patch(f"/admin/users/{user_id_normal}/role", json={"is_admin": False}, headers=admin)
    print("demote:", r.status_code, r.json()["is_admin"], "(expect 200 False)")
print("demoted user blocked again:", c.get("/admin/users", headers=normal).status_code, "(expect 403)")
