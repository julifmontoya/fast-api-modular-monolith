# app/ticket/services.py
from sqlalchemy.orm import Session
from app.ticket.models import Ticket
from app.ticket.schemas import TicketCreate, TicketUpdate

def get_all_tickets(db: Session) -> list[Ticket]:
    return db.query(Ticket).all()

def get_ticket(db: Session, ticket_id: int) -> Ticket | None:
    return db.query(Ticket).filter(Ticket.id == ticket_id).first()

def create_ticket(db: Session, payload: TicketCreate) -> Ticket:
    db_ticket = Ticket(**payload.model_dump())
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket

def update_ticket(db: Session, ticket_id: int, payload: TicketUpdate) -> Ticket | None:
    db_ticket = get_ticket(db, ticket_id)
    if not db_ticket:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(db_ticket, field, value)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket

def delete_ticket(db: Session, ticket_id: int) -> Ticket | None:
    db_ticket = get_ticket(db, ticket_id)
    if not db_ticket:
        return None
    db.delete(db_ticket)
    db.commit()
    return db_ticket
