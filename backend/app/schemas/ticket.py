from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

TicketStatus = Literal["open", "in_progress", "resolved"]


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    message: str
    sentiment: str
    category: str
    source: str
    status: str
    created_at: datetime | None = None


class TicketDetail(TicketOut):
    user_email: str | None = None
    user_name: str | None = None


class TicketStatusUpdate(BaseModel):
    status: TicketStatus
