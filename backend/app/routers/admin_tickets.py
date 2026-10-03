from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.ticket import (
    TicketDetail,
    TicketOut,
    TicketStatus,
    TicketStatusUpdate,
)
from app.services.permissions import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])


def _get_ticket_or_404(db: Session, ticket_id: int) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.get("", response_model=List[TicketOut])
def list_tickets(
    status: Optional[TicketStatus] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Ticket)
    if status:
        query = query.filter(Ticket.status == status)
    if category:
        query = query.filter(Ticket.category == category)
    if source:
        query = query.filter(Ticket.source == source)
    return (
        query.order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = _get_ticket_or_404(db, ticket_id)
    user = db.get(User, ticket.user_id) if ticket.user_id else None
    data = TicketOut.model_validate(ticket).model_dump()
    return TicketDetail(
        **data,
        user_email=user.email if user else None,
        user_name=user.full_name if user else None,
    )


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket_status(
    ticket_id: int, body: TicketStatusUpdate, db: Session = Depends(get_db)
):
    ticket = _get_ticket_or_404(db, ticket_id)
    ticket.status = body.status
    db.commit()
    db.refresh(ticket)
    return ticket
