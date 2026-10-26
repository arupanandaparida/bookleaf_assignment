"""Builds compact, factual context about an author's books for the drafting prompt.
Grounding the model in real numbers (rather than letting it guess) is what makes drafts specific."""
import json
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..constants import PRODUCTION_STAGES
from ..db import db


def inr(n) -> str:
    """Rs amount with Indian digit grouping (e.g. 1,00,000)."""
    s = str(int(n or 0))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return f"Rs {s}"


def _fmt(d: datetime) -> str:
    return f"{d.day} {d:%B %Y}"


def _quarter_end(year: int, q: int) -> datetime:  # q = 0..3
    month = q * 3 + 3
    nxt = datetime(year + (month // 12), month % 12 + 1, 1, tzinfo=timezone.utc)
    return nxt - timedelta(days=1)


def payout_window(now: datetime | None = None) -> str:
    """Quarterly cycle: payout due within 45 days of quarter end."""
    now = now or datetime.now(timezone.utc)
    q = (now.month - 1) // 3
    current_end = _quarter_end(now.year, q)
    prev_end = _quarter_end(now.year - 1, 3) if q == 0 else _quarter_end(now.year, q - 1)
    win = timedelta(days=settings.payout_window_days)
    prev_deadline = prev_end + win
    if now <= prev_deadline + timedelta(days=1):
        return (f"The quarter that ended {_fmt(prev_end)} is being paid out; its payout deadline is {_fmt(prev_deadline)}. "
                f"The following cycle covers the quarter ending {_fmt(current_end)}, payable by {_fmt(current_end + win)}.")
    return (f"The previous payout deadline ({_fmt(prev_deadline)}) has passed. The current quarter ends {_fmt(current_end)} "
            f"and its payout is due by {_fmt(current_end + win)}.")


def _describe_book(b) -> str:
    lines = [f'BOOK "{b["title"]}" ({b["book_id"]}) | genre: {b["genre"]} | ISBN on record: {b["isbn"] or "none"} | status: {b["status"]}']

    if b["status"].startswith("In Production"):
        stage = b["status"].replace("In Production - ", "")
        idx = PRODUCTION_STAGES.index(stage) if stage in PRODUCTION_STAGES else -1
        pos = f" (stage {idx + 1} of {len(PRODUCTION_STAGES)})" if idx >= 0 else ""
        lines.append(f"Not yet published: no sales or royalties exist. Current stage: {stage}{pos}. Publication date and MRP not set yet.")
        lines.append("Exact stage start date and pending approvals are NOT in the data: say the team will confirm.")
        return "\n".join(lines)

    platforms = json.loads(b["available_on"] or "[]")
    lines.append(f'Published {b["publication_date"]} | MRP Rs {b["mrp"]} | print partner: {b["print_partner"]} | listed on: {", ".join(platforms) or "none"}')
    lines.append(f'Sales/royalty: {b["total_copies_sold"]} copies x Rs {b["author_royalty_per_copy"]}/copy = {inr(b["total_royalty_earned"])} earned; '
                 f'{inr(b["royalty_paid"])} paid; {inr(b["royalty_pending"])} pending; last payout: {b["last_royalty_payout_date"] or "never"}')

    paid, pending, thr = b["royalty_paid"], b["royalty_pending"], settings.payout_threshold
    if paid == 0 and pending > 0:
        lines.append(f"No payout yet because pending ({inr(pending)}) is below the Rs {thr} minimum threshold; it rolls over to the next quarter."
                     if pending < thr else
                     f"No payout has ever been made although {inr(pending)} is above the Rs {thr} threshold: check whether this is overdue (possible BookLeaf delay or missing bank details).")
    elif 0 < pending < thr:
        lines.append(f"Pending {inr(pending)} is below the Rs {thr} threshold and rolls over.")
    elif pending == 0:
        lines.append("Nothing pending: all earned royalty has been paid.")
    return "\n".join(lines)


def build_facts(author_id: str, book_id: str | None, now: datetime | None = None) -> str:
    author = db.one("SELECT name, joined_date FROM authors WHERE author_id = ?", (author_id,))
    parts = [f"AUTHOR: {author['name']} (joined {author['joined_date']})"]
    if book_id:
        b = db.one("SELECT * FROM books WHERE book_id = ? AND author_id = ?", (book_id, author_id))
        if b:
            parts.append(_describe_book(b))
    else:
        parts.append("ACCOUNT SUMMARY (one line per book):")
        for b in db.all("SELECT * FROM books WHERE author_id = ?", (author_id,)):
            parts.append(f'- "{b["title"]}": {b["status"]}' if b["status"].startswith("In Production") else
                         f'- "{b["title"]}": {b["total_copies_sold"]} sold, earned {inr(b["total_royalty_earned"])}, paid {inr(b["royalty_paid"])}, pending {inr(b["royalty_pending"])}')
    parts.append(f"PAYOUT CALENDAR: {payout_window(now)}")
    parts.append("NOT AVAILABLE TO YOU (never invent): bank-account link status, per-platform sales split, courier tracking, exact dates of production stages.")
    return "\n".join(parts)
