import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from ..config import settings
from ..db import db
from ..errors import forbidden
from ..schemas import MessageIn, NoteIn, TicketIn, TicketPatch, TicketQuery
from ..security import RateLimit, current_user, current_user_sse, require_admin, require_author
from ..services import events
from ..services import ticket_service as svc

router = APIRouter()
_create_limit = RateLimit(20)
_ai_limit = RateLimit(30)


@router.get("/health")
async def health():
    from datetime import datetime, timezone
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat(), "sseClients": events.client_count()}


@router.get("/tickets")
async def list_tickets(q: Annotated[TicketQuery, Query()], user: dict = Depends(current_user)):
    return svc.list_tickets(user, q.model_dump())


@router.post("/tickets", status_code=201, dependencies=[Depends(_create_limit)])
async def create_ticket(body: TicketIn, user: dict = Depends(require_author)):
    ticket = svc.create_ticket(user, body)
    svc.spawn_classification(ticket["id"])  # returns immediately; classification arrives via SSE
    return ticket


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: int, user: dict = Depends(current_user)):
    return svc.get_ticket(ticket_id, user)


@router.patch("/tickets/{ticket_id}")
async def patch_ticket(ticket_id: int, body: TicketPatch, admin: dict = Depends(require_admin)):
    return svc.update_ticket(ticket_id, body, body.model_fields_set, admin)


@router.post("/tickets/{ticket_id}/messages", status_code=201)
async def post_message(ticket_id: int, body: MessageIn, user: dict = Depends(current_user)):
    if user["role"] == "author" and body.status:
        raise forbidden("Only admins can change ticket status")
    return svc.add_message(ticket_id, user, body.body, body.status)


@router.post("/tickets/{ticket_id}/notes", status_code=201)
async def post_note(ticket_id: int, body: NoteIn, admin: dict = Depends(require_admin)):
    return svc.add_note(ticket_id, admin, body.body)


@router.post("/tickets/{ticket_id}/draft", dependencies=[Depends(_ai_limit)])
async def draft(ticket_id: int, regenerate: bool = False, admin: dict = Depends(require_admin)):
    return {"draft": await svc.get_or_create_draft(ticket_id, force=regenerate)}


@router.post("/tickets/{ticket_id}/reclassify", dependencies=[Depends(_ai_limit)])
async def reclassify(ticket_id: int, admin: dict = Depends(require_admin)):
    return await svc.classify_and_apply(ticket_id, force=True)


# ---------- Admin ----------
@router.get("/admin/stats")
async def stats(admin: dict = Depends(require_admin)):
    return svc.stats()


@router.get("/admin/admins")
async def admins(admin: dict = Depends(require_admin)):
    return {"items": [dict(r) for r in db.all("SELECT id, name, email FROM users WHERE role = 'admin' ORDER BY name")]}


# ---------- Real-time (SSE) ----------
@router.get("/events")
async def stream(request: Request, user: dict = Depends(current_user_sse)):
    sub = events.subscribe(user)

    async def gen():
        try:
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    yield await asyncio.wait_for(sub.queue.get(), timeout=25)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # heartbeat keeps proxies from closing the stream
        finally:
            events.unsubscribe(sub)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"})
