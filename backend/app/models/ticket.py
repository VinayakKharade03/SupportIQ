from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func

from app.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # null = anonymous chat
    message = Column(Text, nullable=False)
    sentiment = Column(String(20), nullable=False)
    category = Column(String(50), nullable=False)
    source = Column(String(10), nullable=False, default="chat")  # chat or voice
    status = Column(String(20), nullable=False, default="open")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
