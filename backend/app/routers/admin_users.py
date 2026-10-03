from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.admin_user import AdminRoleUpdate, AdminUserOut
from app.services.permissions import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("", response_model=List[AdminUserOut])
def list_users(
    search: Optional[str] = None,
    is_admin: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(User.email.ilike(pattern), User.full_name.ilike(pattern))
        )
    if is_admin is not None:
        query = query.filter(User.is_admin == is_admin)
    return query.order_by(User.id).offset(offset).limit(limit).all()


@router.get("/{user_id}", response_model=AdminUserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}/role", response_model=AdminUserOut)
def update_user_role(
    user_id: int,
    body: AdminRoleUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(
            status_code=400, detail="You cannot change your own admin status"
        )
    user.is_admin = body.is_admin
    db.commit()
    db.refresh(user)
    return user
