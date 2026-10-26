"""Domain logic for tickets. Routes stay thin; the AI package knows nothing about HTTP."""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from ..ai.classifier import classify_ticket
from ..ai.drafter import draft_reply
from ..ai.provider import ai_configured, breaker_open
from ..db import db
from ..errors import bad_request, not_found
from . import events

log = logging.getLogger("bookleaf")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def ref(i: int) -> str:
    return f"TKT-{i:04d}"


# Active tickets first, then most urgent, then oldest: the "what should I work on next" order.
URGENCY_ORDER = """
  CASE WHEN t.status IN ('Open','In Progress') THEN 0 ELSE 1 END,
  CASE t.priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 3 WHEN 'Low' THEN 4 ELSE 2 END,
  t.created_at ASC"""

BASE_SELECT = """
  SELECT t.*, a.name AS author_name, a.email AS author_email,
         b.title AS book_title, b.status AS book_status, u.name AS assignee_name,
         (SELECT COUNT(*) FROM messages m WHERE m.ticket_id = t.id) AS message_count
  FROM tickets t
  JOIN authors a ON a.author_id = t.author_id
  LEFT JOIN books b ON b.book_id = t.book_id
  LEFT JOIN users u ON u.id = t.assigned_to"""


def serialize(row, role: str) -> dict:
    base = {
        "id": row["id"], "ref": ref(row["id"]), "subject": row["subject"], "description": row["description"],
        "attachments": json.loads(row["attachments"] or "[]"), "status": row["status"],
        "book": {"id": row["book_id"], "title": row["book_title"]} if row["book_id"] else None,
        "category": row["category"], "messageCount": row["message_count"],
        "createdAt": row["created_at"], "updatedAt": row["updated_at"],
    }
    if role != "admin":
        return base  # authors never see priority, AI reasoning, assignee or notes

    created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
    age_hours = round((datetime.now(timezone.utc) - created).total_seconds() / 3600)
    return {
        **base,
        "author": {"id": row["author_id"], "name": row["author_name"], "email": row["author_email"]},
        "bookStatus": row["book_status"],
        "priority": row["priority"], "categorySource": row["category_source"], "prioritySource": row["priority_source"],
        "aiReasoning": row["ai_reasoning"],
        "assignedTo": {"id": row["assigned_to"], "name": row["assignee_name"]} if row["assigned_to"] else None,
        "firstResponseAt": row["first_response_at"], "ageHours": age_hours,
        "isOverdue": row["status"] in ("Open", "In Progress") and age_hours >= 48,
    }


def _load_row(ticket_id: int):
    row = db.one(f"{BASE_SELECT} WHERE t.id = ?", (ticket_id,))
    if not row:
        raise not_found("Ticket not found")
    return row


def _load_for_user(ticket_id: int, user: dict):
    row = _load_row(ticket_id)
    # Authors get a 404 (not 403) for other people's tickets so ids can't be probed.
    if user["role"] == "author" and row["author_id"] != user["authorId"]:
        raise not_found("Ticket not found")
    return row


def list_tickets(user: dict, f: dict) -> dict:
    where, p = [], {}
    if user["role"] == "author":
        where.append("t.author_id = :authorId"); p["authorId"] = user["authorId"]
    elif f.get("authorId"):
        where.append("t.author_id = :authorId"); p["authorId"] = f["authorId"]

    if f.get("status"): where.append("t.status = :status"); p["status"] = f["status"]
    if user["role"] == "admin":
        if f.get("category"): where.append("t.category = :category"); p["category"] = f["category"]
        if f.get("priority"): where.append("t.priority = :priority"); p["priority"] = f["priority"]
    if f.get("from_"): where.append("t.created_at >= :from_"); p["from_"] = f"{f['from_']}T00:00:00.000Z"
    if f.get("to"): where.append("t.created_at <= :to"); p["to"] = f"{f['to']}T23:59:59.999Z"
    if f.get("assigned") == "me": where.append("t.assigned_to = :me"); p["me"] = user["id"]
    elif f.get("assigned") == "unassigned": where.append("t.assigned_to IS NULL")
    if f.get("q"):
        where.append("(t.subject LIKE :q OR t.description LIKE :q OR a.name LIKE :q)"); p["q"] = f"%{f['q']}%"

    clause = f"WHERE {' AND '.join(where)}" if where else ""
    order = URGENCY_ORDER if user["role"] == "admin" else "t.updated_at DESC"
    rows = db.all(f"{BASE_SELECT} {clause} ORDER BY {order} LIMIT :limit OFFSET :offset",
                  {**p, "limit": f.get("limit", 100), "offset": f.get("offset", 0)})
    total = db.one(f"SELECT COUNT(*) c FROM tickets t JOIN authors a ON a.author_id = t.author_id {clause}", p)["c"]
    return {"items": [serialize(r, user["role"]) for r in rows], "total": total}


def get_ticket(ticket_id: int, user: dict) -> dict:
    row = _load_for_user(ticket_id, user)
    messages = [dict(m) for m in db.all(
        "SELECT id, sender_role AS senderRole, sender_name AS senderName, body, created_at AS createdAt FROM messages WHERE ticket_id = ? ORDER BY id", (ticket_id,))]
    result = {**serialize(row, user["role"]), "messages": messages}
    if user["role"] == "admin":
        result["notes"] = [dict(n) for n in db.all(
            "SELECT id, admin_name AS adminName, body, created_at AS createdAt FROM notes WHERE ticket_id = ? ORDER BY id", (ticket_id,))]
        result["aiDraft"] = ({"text": row["ai_draft"], "source": row["ai_draft_source"], "createdAt": row["ai_draft_at"],
                              "stale": row["ai_draft_msgs"] != len(messages)} if row["ai_draft"] else None)
    return result


def create_ticket(user: dict, data) -> dict:
    if data.bookId and not db.one("SELECT 1 FROM books WHERE book_id = ? AND author_id = ?", (data.bookId, user["authorId"])):
        raise bad_request("Selected book does not belong to your account")
    ts = now()
    tid = db.run(
        "INSERT INTO tickets (author_id, book_id, subject, description, attachments, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (user["authorId"], data.bookId or None, data.subject, data.description,
         json.dumps([a.model_dump() for a in data.attachments]), ts, ts))
    events.publish({"type": "created", "ticketId": tid, "authorId": user["authorId"]})
    return get_ticket(tid, user)


_tasks: set[asyncio.Task] = set()


def spawn_classification(ticket_id: int) -> None:
    """Fire-and-forget: ticket creation never waits on (or fails because of) the AI."""
    async def _run():
        try:
            await classify_and_apply(ticket_id)
        except Exception:  # noqa: BLE001
            log.exception("background classification failed for ticket %s", ticket_id)
    task = asyncio.get_running_loop().create_task(_run())
    _tasks.add(task)  # keep a strong ref so the task isn't garbage-collected mid-flight
    task.add_done_callback(_tasks.discard)


async def classify_and_apply(ticket_id: int, force: bool = False) -> dict:
    """Classify and store, but never overwrite a value an admin has already set (unless forced)."""
    row = _load_row(ticket_id)
    result = await classify_ticket(ticket_id=ticket_id, subject=row["subject"], description=row["description"],
                                   book_title=row["book_title"], book_status=row["book_status"])
    # Re-read inside the write so an admin override that landed during the AI call is never clobbered.
    with db.transaction():
        cur = db.one("SELECT category_source, priority_source FROM tickets WHERE id = ?", (ticket_id,))
        set_cat = force or cur["category_source"] != "admin"
        set_pri = force or cur["priority_source"] != "admin"
        db.run("""UPDATE tickets SET
                    category = CASE WHEN :set_cat THEN :category ELSE category END,
                    category_source = CASE WHEN :set_cat THEN :source ELSE category_source END,
                    priority = CASE WHEN :set_pri THEN :priority ELSE priority END,
                    priority_source = CASE WHEN :set_pri THEN :source ELSE priority_source END,
                    ai_reasoning = :reasoning, updated_at = :ts WHERE id = :id""",
               {"id": ticket_id, "set_cat": int(set_cat), "set_pri": int(set_pri), "category": result["category"],
                "priority": result["priority"], "source": result["source"], "reasoning": result["reasoning"], "ts": now()})
    events.publish({"type": "classified", "ticketId": ticket_id, "authorId": row["author_id"]})
    return get_ticket(ticket_id, {"role": "admin"})


def update_ticket(ticket_id: int, patch, fields_set: set, admin: dict) -> dict:
    row = _load_row(ticket_id)
    sets, p = [], {"id": ticket_id, "ts": now()}
    if patch.status: sets.append("status = :status"); p["status"] = patch.status
    if patch.category: sets.append("category = :category, category_source = 'admin'"); p["category"] = patch.category
    if patch.priority: sets.append("priority = :priority, priority_source = 'admin'"); p["priority"] = patch.priority
    if "assignedTo" in fields_set:
        target = None
        if patch.assignedTo == "me":
            target = admin["id"]
        elif patch.assignedTo is not None:
            if not db.one("SELECT id FROM users WHERE id = ? AND role = 'admin'", (patch.assignedTo,)):
                raise bad_request('assignedTo must be an admin user id, "me", or null')
            target = patch.assignedTo
        sets.append("assigned_to = :assigned"); p["assigned"] = target
    if not sets:
        raise bad_request("No updatable fields supplied")
    db.run(f"UPDATE tickets SET {', '.join(sets)}, updated_at = :ts WHERE id = :id", p)
    events.publish({"type": "updated", "ticketId": ticket_id, "authorId": row["author_id"]})
    return get_ticket(ticket_id, admin)


def add_note(ticket_id: int, admin: dict, body: str) -> dict:
    _load_row(ticket_id)
    db.run("INSERT INTO notes (ticket_id, admin_id, admin_name, body, created_at) VALUES (?,?,?,?,?)", (ticket_id, admin["id"], admin["name"], body, now()))
    db.run("UPDATE tickets SET updated_at = ? WHERE id = ?", (now(), ticket_id))
    events.publish({"type": "note", "ticketId": ticket_id, "authorId": None})  # internal: never reaches authors
    return get_ticket(ticket_id, admin)


def add_message(ticket_id: int, user: dict, body: str, status: str | None) -> dict:
    row = _load_for_user(ticket_id, user)
    ts = now()
    with db.transaction():
        sender = f"{user['name']} (BookLeaf Support)" if user["role"] == "admin" else user["name"]
        if user["role"] == "author" and row["status"] == "Closed":
            raise bad_request("This ticket is closed. Please raise a new query.")
        db.run("INSERT INTO messages (ticket_id, sender_role, sender_id, sender_name, body, created_at) VALUES (?,?,?,?,?,?)",
               (ticket_id, user["role"], user["id"], sender, body, ts))
        if user["role"] == "admin":
            nxt = status or ("In Progress" if row["status"] == "Open" else row["status"])
            db.run("""UPDATE tickets SET status = ?, updated_at = ?, first_response_at = COALESCE(first_response_at, ?),
                      assigned_to = COALESCE(assigned_to, ?) WHERE id = ?""", (nxt, ts, ts, user["id"], ticket_id))
        else:
            # Author follow-up on a resolved ticket reopens it so it reappears in the admin queue.
            db.run("UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?", ("Open" if row["status"] == "Resolved" else row["status"], ts, ticket_id))
    events.publish({"type": "message", "ticketId": ticket_id, "authorId": row["author_id"]})
    return get_ticket(ticket_id, user)


# ---- AI draft: generated on first open, cached, regenerated when stale or forced ----
_inflight: dict[int, asyncio.Task] = {}


async def _make_draft(ticket_id: int, force: bool):
    row = _load_row(ticket_id)
    if not row["category"]:
        await classify_and_apply(ticket_id)
        row = _load_row(ticket_id)
    thread = db.all("SELECT sender_role, body FROM messages WHERE ticket_id = ? ORDER BY id", (ticket_id,))
    if row["ai_draft"] and row["ai_draft_msgs"] == len(thread) and not force:
        return get_ticket(ticket_id, {"role": "admin"})["aiDraft"]
    author = db.one("SELECT name FROM authors WHERE author_id = ?", (row["author_id"],))
    draft = await draft_reply(ticket=dict(row), author_name=author["name"], book_title=row["book_title"], thread=[dict(m) for m in thread])
    db.run("UPDATE tickets SET ai_draft = ?, ai_draft_source = ?, ai_draft_at = ?, ai_draft_msgs = ? WHERE id = ?",
           (draft["text"], draft["source"], now(), len(thread), ticket_id))
    return get_ticket(ticket_id, {"role": "admin"})["aiDraft"]


async def get_or_create_draft(ticket_id: int, force: bool = False):
    if ticket_id in _inflight:  # de-dupe concurrent opens (cost control)
        return await asyncio.shield(_inflight[ticket_id])
    task = asyncio.ensure_future(_make_draft(ticket_id, force))
    _inflight[ticket_id] = task
    try:
        return await task
    finally:
        _inflight.pop(ticket_id, None)


def stats() -> dict:
    c = lambda sql, *a: db.one(sql, a)["c"]  # noqa: E731
    calls = db.one("""SELECT COUNT(*) calls, COALESCE(SUM(ok),0) ok, COALESCE(SUM(input_tokens),0) inTok,
                      COALESCE(SUM(output_tokens),0) outTok, COALESCE(AVG(CASE WHEN ok=1 THEN latency_ms END),0) avgMs FROM ai_calls""")
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return {
        "tickets": {
            "open": c("SELECT COUNT(*) c FROM tickets WHERE status = 'Open'"),
            "inProgress": c("SELECT COUNT(*) c FROM tickets WHERE status = 'In Progress'"),
            "unassigned": c("SELECT COUNT(*) c FROM tickets WHERE assigned_to IS NULL AND status IN ('Open','In Progress')"),
            "critical": c("SELECT COUNT(*) c FROM tickets WHERE priority = 'Critical' AND status IN ('Open','In Progress')"),
            "overdue": c("SELECT COUNT(*) c FROM tickets WHERE status IN ('Open','In Progress') AND created_at <= ?", cutoff),
        },
        "ai": {"configured": ai_configured(), "circuitOpen": breaker_open(), "calls": calls["calls"],
               "failures": calls["calls"] - calls["ok"], "inputTokens": calls["inTok"], "outputTokens": calls["outTok"],
               "avgLatencyMs": round(calls["avgMs"])},
    }
