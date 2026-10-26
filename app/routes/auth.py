from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from ..config import settings
from ..constants import CATEGORIES, PRIORITIES, STATUSES
from ..db import db
from ..errors import unauthorized
from ..schemas import LoginIn
from ..security import RateLimit, current_user, sign_token, verify_password

router = APIRouter()


@router.post("/auth/login", dependencies=[Depends(RateLimit(settings.login_rate_limit))])
async def login(body: LoginIn):
    user = db.one("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (body.email,))
    # Same message for unknown email and wrong password: don't leak which accounts exist.
    # bcrypt is CPU-bound, so run it off the event loop.
    if not user or not await run_in_threadpool(verify_password, body.password, user["password_hash"]):
        raise unauthorized("Incorrect email or password")
    return {"token": sign_token(user["id"], user["role"]),
            "user": {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"], "authorId": user["author_id"]}}


@router.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    return {"user": user}


@router.get("/meta")
async def meta(_: dict = Depends(current_user)):
    return {"categories": CATEGORIES, "priorities": PRIORITIES, "statuses": STATUSES}
