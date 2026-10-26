"""Deterministic, zero-cost fallbacks used when the LLM is unavailable (no key, rate-limited, down, or bad output).
Tickets are ALWAYS classified and drafts ALWAYS available; quality is lower, and the UI labels them as such."""
import re

_I = re.IGNORECASE
RULES = [
    ("ISBN & Metadata Issues", re.compile(r"\bisbn\b|duplicate|wrong book|metadata|different (title|isbn)", _I)),
    ("Printing & Quality", re.compile(r"print|blurry|misalign|binding|misprint|quality|colou?r|reprint|defect|torn|faded", _I)),
    ("Distribution & Availability", re.compile(r"unavailable|out of stock|not (showing|listed|available)|amazon|flipkart|listing|listed|distribution|sync", _I)),
    ("Royalty & Payments", re.compile(r"royalt|payment|payout|paid|bank|earn|money|rs\.?\s?\d|₹", _I)),
    ("Book Status & Production Updates", re.compile(r"typesetting|cover design|proof|editing|production|when will|how long|status|stage|delay", _I)),
]
CRITICAL = re.compile(r"legal|lawyer|court|fraud|scam|cheat|consumer forum|refund|chargeback", _I)
HIGH = re.compile(r"(\b[6-9]|\b1\d)\s*months?|haven'?t received|not received|never received|no royalty|wrong isbn|duplicate|terrible|urgent|asap|immediately|unavailable", _I)
LOW = re.compile(r"can i|how (do|can)|update.*(bio|description)|just (wondering|curious)|question about", _I)
ISBN_ERR = re.compile(r"wrong|different|duplicate|mismatch|error", _I)


def rule_classify(subject: str = "", description: str = "") -> dict:
    text = f"{subject} {description}"
    category = next((c for c, rx in RULES if rx.search(text)), "General Inquiry")

    priority = "Medium"
    if CRITICAL.search(text):
        priority = "Critical"
    elif HIGH.search(text):
        priority = "High"
    elif LOW.search(text):
        priority = "Low"

    if category == "ISBN & Metadata Issues" and ISBN_ERR.search(text) and priority not in ("Critical", "High"):
        priority = "High"  # KB: author-reported ISBN errors are high priority
    if category == "General Inquiry" and priority == "Medium":
        priority = "Low"
    return {"category": category, "priority": priority, "reasoning": "Rule-based classification (AI unavailable)."}


def template_draft(category: str | None, author_name: str, book_title: str | None) -> str:
    first = (author_name or "").split(" ")[0] or "there"
    book = f'"{book_title}"' if book_title else "your account"
    bodies = {
        "Royalty & Payments": f"Thank you for reaching out, and I understand how important clarity on royalties is. Royalties are calculated quarterly and paid by bank transfer within 45 days of the quarter ending; payouts below Rs 1,000 roll over to the next quarter. I am checking the details for {book} right now, and I will send you a line-by-line royalty breakdown within 48 hours. If you notice anything in your dashboard that does not match, please reply here and we will look at it together.",
        "ISBN & Metadata Issues": f"Thank you for flagging this. An ISBN problem on {book} is a serious data issue and we are treating it as high priority. I am escalating it to our production team right now. You will hear back from us with a resolution within 48 hours. If you have a screenshot of the listing or a photo of the copyright page, please reply with it so we can move faster.",
        "Printing & Quality": f"I am really sorry that your copies of {book} did not meet the quality you expect, and we want to put this right. Could you share a few photos of the defective copies in reply? Once we verify them, we will arrange a free reprint, which takes 5-7 business days from confirmation.",
        "Distribution & Availability": f"Thank you for letting us know. This usually points to a stock sync issue on the platform. I am asking our distribution team to trigger a re-sync for {book} today, and it should be live again within 24-48 hours. If it is still unavailable after that, reply here and I will follow up personally.",
        "Book Status & Production Updates": f"Thank you for checking in on {book}. I am confirming the exact stage and what is pending with our production team, and I will send you a specific updated timeline within 48 hours. Delays are most often at cover design or proofreading while we wait on approvals, and we will work through the next step together.",
        "General Inquiry": f"Thank you for your message. I am looking into this for {book} and will get back to you with a clear answer within 48 hours. If there is anything else that would help us respond faster, please reply to this message.",
    }
    return f"Hi {first},\n\n{bodies.get(category or 'General Inquiry', bodies['General Inquiry'])}\n\nWarm regards,\nTeam BookLeaf"
