from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None = None
    is_admin: bool
    created_at: datetime | None = None


class AdminRoleUpdate(BaseModel):
    is_admin: bool
