from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.user import User
from app.services.security import create_access_token

c = TestClient(app)


def token_for(email):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise SystemExit(f"User {email} not found")
        token = create_access_token({"sub": str(user.id)})
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


user = token_for("user@example.com")
admin = token_for("admin@gmail.com")

print("no token:", c.get("/admin/tickets").status_code, "(expect 401)")
print("normal user list:", c.get("/admin/tickets", headers=user).status_code, "(expect 403)")
print("normal user patch:", c.patch("/admin/tickets/1", json={"status": "resolved"}, headers=user).status_code, "(expect 403)")

r = c.get("/admin/tickets", headers=admin)
tickets = r.json()
print("admin list:", r.status_code, "count:", len(tickets))
if tickets:
    tid = tickets[0]["id"]
    orig = tickets[0]["status"]
    print("detail:", c.get(f"/admin/tickets/{tid}", headers=admin).json())
    print("bad status:", c.patch(f"/admin/tickets/{tid}", json={"status": "nonsense"}, headers=admin).status_code, "(expect 422)")
    print("set in_progress:", c.patch(f"/admin/tickets/{tid}", json={"status": "in_progress"}, headers=admin).json()["status"])
    print("restore:", c.patch(f"/admin/tickets/{tid}", json={"status": orig}, headers=admin).json()["status"])
print("missing ticket:", c.get("/admin/tickets/99999", headers=admin).status_code, "(expect 404)")
print("filtered count:", len(c.get("/admin/tickets?status=open&source=chat", headers=admin).json()))
