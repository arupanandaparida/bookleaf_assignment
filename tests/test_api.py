import json

from .conftest import FakeAI, auth, login, wait_for


def test_login_succeeds_fails_generically_and_validates(client):
    assert login(client, "ananya.reddy@email.com", "Author@123")
    bad = client.post("/api/auth/login", json={"email": "ananya.reddy@email.com", "password": "nope"})
    assert bad.status_code == 401
    unknown = client.post("/api/auth/login", json={"email": "ghost@email.com", "password": "nope"})
    assert unknown.json() == bad.json(), "must not reveal whether the email exists"
    invalid = client.post("/api/auth/login", json={"email": "not-an-email", "password": "x"})
    assert invalid.status_code == 400 and invalid.json()["error"]["code"] == "VALIDATION_ERROR"


def test_all_routes_require_authentication(client):
    for p in ("/api/books", "/api/tickets", "/api/admin/stats"):
        assert client.get(p).status_code == 401, p


def test_author_sees_only_own_books_including_in_production(client):
    t = login(client, "kavita.deshmukh@email.com", "Author@123")
    items = client.get("/api/books", headers=auth(t)).json()["items"]
    assert len(items) == 2 and all(b["authorId"] == "AUTH009" for b in items)
    by_id = {b["id"]: b for b in items}
    assert by_id["BK015"]["inProduction"] is True
    assert by_id["BK016"]["belowPayoutThreshold"] is True  # Rs 850 < Rs 1,000
    sneaky = client.get("/api/books?authorId=AUTH001", headers=auth(t)).json()["items"]
    assert all(b["authorId"] == "AUTH009" for b in sneaky)
    assert client.get("/api/books/BK001", headers=auth(t)).status_code == 404


def test_rbac(client):
    a = login(client, "priya.sharma@email.com", "Author@123")
    assert client.get("/api/admin/stats", headers=auth(a)).status_code == 403
    admin = login(client, "admin@bookleaf.com", "Admin@123")
    assert client.get("/api/admin/stats", headers=auth(admin)).status_code == 200
    assert client.post("/api/tickets", headers=auth(admin), json={"subject": "hello there", "description": "x" * 30}).status_code == 403


def test_ticket_lifecycle(client):
    author = login(client, "ananya.reddy@email.com", "Author@123")
    admin = login(client, "admin@bookleaf.com", "Admin@123")

    bad = client.post("/api/tickets", headers=auth(author), json={"subject": "x", "description": "short"})
    assert bad.status_code == 400
    assert {d["field"] for d in bad.json()["error"]["details"]} == {"subject", "description"}
    foreign = client.post("/api/tickets", headers=auth(author), json={"bookId": "BK001", "subject": "Not my book", "description": "This book is not on my account at all."})
    assert foreign.status_code == 400

    created = client.post("/api/tickets", headers=auth(author), json={
        "bookId": "BK005", "subject": "Royalty not received",
        "description": "I have not received any royalty for my book in four months. Please help."})
    assert created.status_code == 201
    tid = created.json()["id"]
    assert "priority" not in created.json(), "authors must not see priority"

    t = wait_for(lambda: (r := client.get(f"/api/tickets/{tid}", headers=auth(admin)).json())["categorySource"] == "ai" and r)
    assert (t["category"], t["priority"]) == ("Royalty & Payments", "High")

    ov = client.patch(f"/api/tickets/{tid}", headers=auth(admin), json={"priority": "Critical", "category": "General Inquiry"}).json()
    assert ov["prioritySource"] == "admin" and ov["categorySource"] == "admin"
    assert client.patch(f"/api/tickets/{tid}", headers=auth(admin), json={"priority": "Urgent!"}).status_code == 400
    assert client.patch(f"/api/tickets/{tid}", headers=auth(admin), json={}).status_code == 400
    me = client.patch(f"/api/tickets/{tid}", headers=auth(admin), json={"category": "Royalty & Payments", "assignedTo": "me"}).json()
    assert me["assignedTo"]["name"].startswith("Riya")

    d = client.post(f"/api/tickets/{tid}/draft", headers=auth(admin)).json()["draft"]
    assert d["source"] == "ai"
    before = len(FakeAI.calls)
    client.post(f"/api/tickets/{tid}/draft", headers=auth(admin))
    assert len(FakeAI.calls) == before, "second open must be served from cache"

    prompt = next(c for c in FakeAI.calls if "triage" not in c["system"])["messages"][0]["content"]
    assert "ROYALTY POLICY" in prompt and "ISBN POLICY" not in prompt  # only the relevant KB section
    assert "Between Two Temples" in prompt

    client.post(f"/api/tickets/{tid}/notes", headers=auth(admin), json={"body": "INTERNAL: verify bank KYC"})
    reply = client.post(f"/api/tickets/{tid}/messages", headers=auth(admin), json={"body": d["text"], "status": "In Progress"}).json()
    assert reply["status"] == "In Progress"

    view = client.get(f"/api/tickets/{tid}", headers=auth(author)).json()
    assert len(view["messages"]) == 1 and view["messages"][0]["senderRole"] == "admin"
    assert "INTERNAL" not in json.dumps(view) and "notes" not in view

    other = login(client, "priya.sharma@email.com", "Author@123")
    assert client.get(f"/api/tickets/{tid}", headers=auth(other)).status_code == 404

    # author follow-up on a resolved ticket reopens it; Closed rejects
    client.patch(f"/api/tickets/{tid}", headers=auth(admin), json={"status": "Resolved"})
    client.post(f"/api/tickets/{tid}/messages", headers=auth(author), json={"body": "Still not solved, please check."})
    assert client.get(f"/api/tickets/{tid}", headers=auth(author)).json()["status"] == "Open"
    client.patch(f"/api/tickets/{tid}", headers=auth(admin), json={"status": "Closed"})
    assert client.post(f"/api/tickets/{tid}/messages", headers=auth(author), json={"body": "Hello again"}).status_code == 400
    assert client.post(f"/api/tickets/{tid}/messages", headers=auth(author), json={"body": "hi there", "status": "Closed"}).status_code in (400, 403)


def test_ai_outage_degrades_gracefully(client):
    FakeAI.mode = "down"
    try:
        author = login(client, "arjun.malhotra@email.com", "Author@123")
        admin = login(client, "admin@bookleaf.com", "Admin@123")
        r = client.post("/api/tickets", headers=auth(author), json={
            "bookId": "BK010", "subject": "Wrong ISBN on my book",
            "description": "The ISBN on Amazon is different from the physical copy of my book."})
        assert r.status_code == 201, "ticket must be created even when AI is down"
        tid = r.json()["id"]
        t = wait_for(lambda: (x := client.get(f"/api/tickets/{tid}", headers=auth(admin)).json())["categorySource"] == "rules" and x)
        assert (t["category"], t["priority"]) == ("ISBN & Metadata Issues", "High")
        draft = client.post(f"/api/tickets/{tid}/draft", headers=auth(admin))
        assert draft.status_code == 200
        assert draft.json()["draft"]["source"] == "template" and "48 hours" in draft.json()["draft"]["text"]
    finally:
        FakeAI.mode = "ok"


def test_queue_sorted_by_urgency_and_filterable(client):
    admin = login(client, "admin@bookleaf.com", "Admin@123")
    items = client.get("/api/tickets?status=Open", headers=auth(admin)).json()["items"]
    rank = {"Critical": 0, "High": 1, "Medium": 3, "Low": 4}
    r = [rank.get(t["priority"], 2) for t in items]
    assert r == sorted(r)
    assert client.get("/api/tickets?status=Bogus", headers=auth(admin)).status_code == 400
    by_cat = client.get("/api/tickets", params={"category": "Printing & Quality"}, headers=auth(admin)).json()["items"]
    assert by_cat and all(t["category"] == "Printing & Quality" for t in by_cat)
    dated = client.get("/api/tickets?from=2999-01-01", headers=auth(admin)).json()
    assert dated["total"] == 0


def test_unknown_api_route_returns_json_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
