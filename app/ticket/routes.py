# app/ticket/routes.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.ticket.schemas import TicketCreate, TicketOut, TicketUpdate
from app.ticket import services as ticket_service
from app.core.config import get_settings,Settings
router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.get("/papo")
def papo(settings: Settings = Depends(get_settings)):
    return {
        "message": "Hello from /test route!",
        "secret_key": settings.ENV_,  # (don’t expose secrets in real apps)
    }

@router.post("/", response_model=TicketOut, status_code=201)
def create(ticket: TicketCreate, db: Session = Depends(get_db)):
    return ticket_service.create_ticket(db, ticket)

@router.get("/", response_model=list[TicketOut])
def list_all(
    status: str | None = Query(default=None, description="Filter by status: open or closed"),
    db: Session = Depends(get_db),
):
    items = ticket_service.get_all_tickets(db)
    if status:
        items = [t for t in items if t.status == status]
    return items


@router.get("/{ticket_id}", response_model=TicketOut)
def get(ticket_id: int, db: Session = Depends(get_db)):
    ticket = ticket_service.get_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.put("/{ticket_id}", response_model=TicketOut)
def update(ticket_id: int, ticket: TicketUpdate, db: Session = Depends(get_db)):
    updated = ticket_service.update_ticket(db, ticket_id, ticket)
    if not updated:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return updated


@router.delete("/{ticket_id}", response_model=TicketOut)
def delete(ticket_id: int, db: Session = Depends(get_db)):
    deleted = ticket_service.delete_ticket(db, ticket_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return deleted
