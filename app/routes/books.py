import json

from fastapi import APIRouter, Depends

from ..config import settings
from ..db import db
from ..errors import not_found
from ..security import current_user

router = APIRouter()


def to_book(b) -> dict:
    return {
        "id": b["book_id"], "authorId": b["author_id"], "title": b["title"], "isbn": b["isbn"], "genre": b["genre"],
        "publicationDate": b["publication_date"], "status": b["status"], "inProduction": b["status"].startswith("In Production"),
        "mrp": b["mrp"], "royaltyPerCopy": b["author_royalty_per_copy"], "copiesSold": b["total_copies_sold"],
        "royaltyEarned": b["total_royalty_earned"], "royaltyPaid": b["royalty_paid"], "royaltyPending": b["royalty_pending"],
        "lastPayoutDate": b["last_royalty_payout_date"], "printPartner": b["print_partner"],
        "availableOn": json.loads(b["available_on"] or "[]"),
        "belowPayoutThreshold": 0 < b["royalty_pending"] < settings.payout_threshold,
    }


@router.get("/books")
async def list_books(authorId: str | None = None, user: dict = Depends(current_user)):
    # Authors are hard-scoped to their own author_id; the query string cannot widen that.
    scope = user["authorId"] if user["role"] == "author" else authorId
    if scope:
        rows = db.all("SELECT * FROM books WHERE author_id = ? ORDER BY publication_date IS NULL, publication_date DESC", (scope,))
    else:
        rows = db.all("SELECT * FROM books ORDER BY author_id, book_id")
    return {"items": [to_book(r) for r in rows]}


@router.get("/books/{book_id}")
async def get_book(book_id: str, user: dict = Depends(current_user)):
    b = db.one("SELECT * FROM books WHERE book_id = ?", (book_id,))
    if not b or (user["role"] == "author" and b["author_id"] != user["authorId"]):
        raise not_found("Book not found")
    return to_book(b)
