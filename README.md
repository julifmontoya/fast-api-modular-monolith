# Fast-API Modular Monolith

## Run app
```
uvicorn app.main:app --reload
```

## 1. Folder Structure
```
app/
  core/                 # shared infra (db, config, middlewares)
    database.py         # engine, SessionLocal, Base, get_db()
    config.py           # environment variables, settings
    logging.py          # (optional) centralized logging config
  ticket/               # Ticket domain (isolated business logic)
    models.py           # SQLAlchemy models for tickets
    schemas.py          # Pydantic models for input/output
    routes.py           # FastAPI APIRouter with endpoints
    services.py         # CRUD & business rules for tickets
  __init__.py
  main.py               # app factory, CORS, routers
tests/                  # pytest tests
```

## Requirements & Install
```
# requirements.txt
fastapi
uvicorn
sqlalchemy
pydantic
pydantic-settings
pytest
httpx
```

```
python -m venv venv
venv\Scripts\activate 
pip install -r requirements.txt
```

## Run the app
```
uvicorn app.main:app --reload
```

## Swagger / OpenAPI Docs
```
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
```

## 2. Core Settings (env & DI) — app/core/config.py
centralizes environment variables and app metadata.
- BaseSettings loads values from .env (and env vars).
- @lru_cache makes get_settings() fast and safe to inject with Depends.

```
# app/core/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    DATABASE_URL: str = Field(default="sqlite:///./tickets.db")
    APP_NAME: str = "Smart Issue Tracker API"
    APP_DESC: str = "A mini ticket system with FastAPI"
    APP_VERSION: str = "1.0.0"
    ENV_: str | None = None  # optional

    # Pydantic v2 style config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()

__all__ = ["Settings", "get_settings"]
```

## 3. Database (engine & sessions) — app/core/database.py
Creates the SQLAlchemy engine & a short-lived session per request.

```
# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Common DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```


## 4. App Entry —  app/__init__.py
```
# app/__init__.py
__all__ = ["core", "ticket"]
```

## 5. App Entry (CORS & Routers) — app/main.py
builds the app, applies CORS, registers routers, and prepares the DB.
- CORS belongs here (global), before requests hit routers.
- Base.metadata.create_all(bind=engine) creates tables for simple demos. In real projects use Alembic migrations.

```
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import Base, engine
from app.ticket.routes import router as ticket_router

Base.metadata.create_all(bind=engine)

settings = get_settings()
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESC,
    version=settings.APP_VERSION,
)

# 👇 CORS setup here
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # or ["*"] to allow all
    allow_credentials=True,
    allow_methods=["*"],          # GET, POST, PUT, DELETE, OPTIONS...
    allow_headers=["*"],
)

# Routers
app.include_router(ticket_router)

@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
```

## 5. Ticket Domain — models, schemas, services, routes

### 5.1 Models (DB layer) — app/ticket/models.py
Purpose: database structure only (no HTTP here).

```
# app/ticket/models.py
from sqlalchemy import Column, Integer, String
from app.core.database import Base

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(String, nullable=False)
    status = Column(String, default="open", index=True)
```

### 5.2 Schemas (I/O contracts) — app/ticket/schemas.py
Purpose: validate inputs and shape outputs.
- Separate create/update from output so you never leak fields like secrets.

```
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
```

### 5.3 Services (business logic) — app/ticket/services.py
Purpose: Pure Python use-cases. Knows about DB & models, doesn’t know HTTP.

```
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
```

### 5.4 Routes (HTTP layer) — app/ticket/routes.py
Purpose: define endpoints, validate input, call services, shape responses.

```
# app/ticket/routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.ticket.schemas import TicketCreate, TicketOut, TicketUpdate
from app.ticket import services as ticket_service
from app.core.config import get_settings,Settings
router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.get("/env")
def env(settings: Settings = Depends(get_settings)):
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
```

## 6. Endpoints 
```
POST /tickets – Create a new ticket
GET /tickets – List all tickets
GET /tickets/{ticket_id} – Get a single ticket
PUT /tickets/{ticket_id} – Update a ticket
DELETE /tickets/{ticket_id} – Delete a ticket
```

## 7. Tests
In app/tests/conftest
```
# tests/conftest.py
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
```

```
# tests/test_tickets.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_and_get_ticket():
    r = client.post("/tickets", json={"title": "T1", "description": "D1"})
    assert r.status_code == 201
    tid = r.json()["id"]

    r2 = client.get(f"/tickets/{tid}")
    assert r2.status_code == 200
    data = r2.json()
    assert data["title"] == "T1"
    assert data["description"] == "D1"
    assert data["status"] == "open"


def test_list_returns_array():
    r = client.get("/tickets")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_update_ticket_title_and_status():
    # create
    r = client.post("/tickets", json={"title": "To Update", "description": "Body"})
    assert r.status_code == 201
    tid = r.json()["id"]

    # update title + status
    r2 = client.put(f"/tickets/{tid}", json={"title": "Updated", "status": "closed"})
    assert r2.status_code == 200
    data = r2.json()
    assert data["id"] == tid
    assert data["title"] == "Updated"
    assert data["status"] == "closed"

    # fetch again to be sure
    r3 = client.get(f"/tickets/{tid}")
    assert r3.status_code == 200
    assert r3.json()["status"] == "closed"


def test_delete_ticket_then_404():
    # create
    r = client.post("/tickets", json={"title": "To Delete", "description": "D"})
    assert r.status_code == 201
    tid = r.json()["id"]

    # delete
    r2 = client.delete(f"/tickets/{tid}")
    assert r2.status_code == 200
    assert r2.json()["id"] == tid

    # now 404
    r3 = client.get(f"/tickets/{tid}")
    assert r3.status_code == 404
    assert r3.json()["detail"] == "Ticket not found"


def test_get_not_found_returns_404():
    # very large id that likely doesn't exist
    r = client.get("/tickets/9999999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Ticket not found"


def test_create_validation_errors():
    # missing title
    r1 = client.post("/tickets", json={"description": "no title"})
    assert r1.status_code == 422

    # missing description
    r2 = client.post("/tickets", json={"title": "no description"})
    assert r2.status_code == 422

    # empty strings (fails min_length=1)
    r3 = client.post("/tickets", json={"title": "", "description": ""})
    assert r3.status_code == 422


def test_filter_by_status_open_only():
    # create two tickets
    a = client.post("/tickets", json={"title": "A", "description": "A"}).json()
    b = client.post("/tickets", json={"title": "B", "description": "B"}).json()

    # close one of them
    client.put(f"/tickets/{b['id']}", json={"status": "closed"})

    # fetch only open
    r = client.get("/tickets?status=open")
    assert r.status_code == 200
    ids = {t["id"] for t in r.json()}
    # 'a' should be present, 'b' should not
    assert a["id"] in ids
    assert b["id"] not in ids
```

## 8. Run Tests
```
pytest -q
```