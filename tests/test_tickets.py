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
