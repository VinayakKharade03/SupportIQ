from fastapi import Depends, HTTPException

from app.models.user import User
from app.routers.orders import get_current_user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
