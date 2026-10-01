from sqlalchemy.orm import Session

from app.models.ticket import Ticket
from app.models.user import User

ESCALATION_CATEGORIES = ("recurring_issue", "refund_request")


def should_escalate(sentiment, category) -> bool:
    return str(sentiment) == "negative" and str(category) in ESCALATION_CATEGORIES


def create_ticket(db: Session, user: User | None, message: str, sentiment, category, source: str) -> Ticket:
    ticket = Ticket(
        user_id=user.id if user else None,
        message=message[:2000],
        sentiment=str(sentiment),
        category=str(category),
        source=source,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket
