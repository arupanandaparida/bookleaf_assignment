"""Seeds the provided dataset (10 authors / 18 books) plus a few demo tickets built from the assignment's sample queries.
Demo tickets are classified through the real rule-based path (no API key needed) and tagged source='rules'."""
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .ai.fallback import rule_classify
from .config import settings
from .db import db
from .security import hash_password

log = logging.getLogger("bookleaf")
DATA_FILE = Path(__file__).parent / "data" / "bookleaf_sample_data.json"

ADMINS = [("admin@bookleaf.com", "Riya (Ops Lead)"), ("support@bookleaf.com", "Aman (Support)")]

DEMO_TICKETS = [
    ("AUTH003", "BK005", 80, "No royalty received since publishing", "I published Between Two Temples about 4 months ago and still have not received any royalty. What is going on? I have sold a few dozen copies according to my dashboard."),
    ("AUTH001", "BK001", 30, "Royalty amount seems too low", "My royalty amount seems too low. I sold over 300 copies of Whispers of the Ganges but my total payout so far is only Rs 8,400. Can you explain how this is calculated?"),
    ("AUTH007", "BK011", 20, "Different ISBN on Amazon vs physical copy", "The Algorithm of Love is showing a different ISBN on Amazon than the one printed on my physical copy. This is causing confusion for readers who try to order it."),
    ("AUTH010", "BK017", 8, "Author copies print quality is terrible", "I received my author copies of Durga’s Daughters and the print quality is terrible. The images are blurry and several pages are misaligned."),
    ("AUTH004", "BK006", 5, "Book showing Currently Unavailable on Amazon", "Debugging Life is published but it is showing as Currently Unavailable on Amazon India since yesterday. Please help."),
    ("AUTH009", "BK015", 3, "Still in typesetting after 3 weeks", "It has been 3 weeks and Raising Roots is still in typesetting. When will it be done?"),
    ("AUTH006", None, 1, "Updating my book description", "Can I update the description of my book on Amazon after it is already live? Just wondering how it works."),
]


def _seed() -> dict:
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    author_hash = hash_password(settings.seed_author_password)
    admin_hash = hash_password(settings.seed_admin_password)
    n_books = 0
    with db.transaction():
        for a in raw["authors"]:
            db.run("INSERT INTO authors (author_id, name, email, phone, city, joined_date) VALUES (?,?,?,?,?,?)",
                   (a["author_id"], a["name"], a["email"], a["phone"], a["city"], a["joined_date"]))
            db.run("INSERT INTO users (email, password_hash, name, role, author_id) VALUES (?,?,?,?,?)",
                   (a["email"], author_hash, a["name"], "author", a["author_id"]))
            for b in a["books"]:
                n_books += 1
                db.run("INSERT INTO books VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    b["book_id"], a["author_id"], b["title"], b["isbn"], b["genre"], b["publication_date"], b["status"], b["mrp"],
                    b["author_royalty_per_copy"], b["total_copies_sold"], b["total_royalty_earned"], b["royalty_paid"],
                    b["royalty_pending"], b["last_royalty_payout_date"], b["print_partner"], json.dumps(b.get("available_on") or [])))
        for email, name in ADMINS:
            db.run("INSERT INTO users (email, password_hash, name, role, author_id) VALUES (?,?,?,?,NULL)", (email, admin_hash, name, "admin"))

        for author, book, hours_ago, subject, desc in DEMO_TICKETS:
            c = rule_classify(subject, desc)
            ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            db.run("""INSERT INTO tickets (author_id, book_id, subject, description, category, category_source, priority, priority_source,
                      ai_reasoning, created_at, updated_at) VALUES (?,?,?,?,?,'rules',?,'rules',?,?,?)""",
                   (author, book, subject, desc, c["category"], c["priority"], c["reasoning"], ts, ts))
    return {"authors": len(raw["authors"]), "books": n_books, "tickets": len(DEMO_TICKETS)}


def seed_if_empty() -> dict | None:
    if db.one("SELECT COUNT(*) c FROM users")["c"] > 0:
        return None
    out = _seed()
    log.info("[seed] loaded %(authors)s authors, %(books)s books, %(tickets)s demo tickets", out)
    return out


def reset() -> None:
    for t in ("ai_calls", "notes", "messages", "tickets", "books", "users", "authors"):
        db.run(f"DELETE FROM {t}")


if __name__ == "__main__":  # python -m app.seed [--reset]
    logging.basicConfig(level=logging.INFO)
    if "--reset" in sys.argv:
        reset()
        print("[seed] database cleared")
    print("[seed] done" if seed_if_empty() else "[seed] database already has data; use --reset to reseed")
