# app/ticket/schemas.py
from pydantic import BaseModel, Field

class TicketBase(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)

class TicketCreate(TicketBase):
    pass

class TicketUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None

class TicketOut(TicketBase):
    id: int
    status: str

    model_config = {"from_attributes": True}
