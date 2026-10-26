"""BookLeaf Knowledge Base split into sections so each AI call only receives what it needs (cost control).
CORE goes into every draft; one category section is added on demand."""

CORE = """COMPANY: BookLeaf Publishing is a self-publishing company in India and the US. Packages: Standard Free (no upfront cost) and Bestseller Breakthrough (paid, with marketing and distribution add-ons). BookLeaf handles cover design, typesetting, ISBN assignment, printing, distribution and royalty management. In-house printing facility and warehouse are in Delhi; print partners are Repro India and Epitome Books.

TONE: Empathetic and professional; authors are partners, not customers to be managed. Acknowledge the concern before solutions. Be specific (real numbers, dates, statuses) instead of vague reassurance. If it is BookLeaf's fault (delayed royalty, ISBN error) own it directly with no corporate deflection. If escalation/investigation is needed, give a clear timeline (e.g. "within 48 hours"), never open-ended promises. Always end with a clear next step."""

SECTIONS = {
    "Royalty & Payments": """ROYALTY POLICY:
- 80/20 split: 80% of net profit per book to the author, 20% to BookLeaf.
- Net profit = MRP minus printing cost, platform commission (Amazon/Flipkart) and shipping charges.
- Royalties are calculated quarterly and paid within 45 days of the quarter ending.
- Minimum payout threshold is Rs 1,000. Below it, royalties roll over to the next quarter.
- Payouts are by bank transfer to the account linked in the author's dashboard.
- Authors can see a detailed royalty breakdown (sales per platform) in their dashboard.""",
    "ISBN & Metadata Issues": """ISBN POLICY:
- Every book gets a unique ISBN assigned by BookLeaf, registered under BookLeaf's publisher imprint. An author who wants an ISBN under their own imprint must obtain it independently.
- An author-reported ISBN error (duplicate, wrong book linked) is HIGH PRIORITY and is escalated to the production team.
- Metadata updates (e.g. description) can be submitted via the dashboard or by emailing the BookLeaf team; changes typically reflect on platforms within 3-5 business days.""",
    "Printing & Quality": """PRINTING & QUALITY:
- In-house printing handles most orders. Overflow or specific format needs go to Repro India or Epitome Books.
- Standard print turnaround: 5-7 business days from order confirmation.
- For quality issues (misprints, binding defects, colour inconsistency) BookLeaf arranges a FREE reprint after verification. The author may need to share photos of the defective copy.""",
    "Distribution & Availability": """DISTRIBUTION:
- Books are listed on Amazon India, Flipkart, Amazon US, Amazon UK and the BookLeaf Store.
- New listings typically go live 7-10 business days after publication is complete.
- A book showing as unavailable on a platform usually indicates a stock sync issue; the team can trigger a re-sync, which takes 24-48 hours.
- Metadata changes reflect on platforms within 3-5 business days.""",
    "Book Status & Production Updates": """PRODUCTION STAGES: Manuscript Received -> Editing (if opted) -> Cover Design -> Typesetting -> Proofreading -> ISBN Assignment -> Printing -> Distribution Setup -> Published & Live.
- Authors are updated by email at each stage.
- Delays typically happen at Cover Design (waiting for author approval) and Proofreading (revision rounds). Frame delays collaboratively; never blame the author.
- New listings go live 7-10 business days after publication is complete.""",
    "General Inquiry": """GENERAL:
- Metadata updates (e.g. book description) can be submitted via the dashboard or by emailing the BookLeaf team; changes typically reflect on platforms within 3-5 business days.
- If you are not sure about something, say the team will confirm and give a 48-hour timeline.""",
}

# One calibration pattern per category, distilled from the assignment's sample queries.
EXAMPLES = {
    "Royalty & Payments": """Pattern A (no royalty received): acknowledge the frustration; explain the quarterly cycle and 45-day window; confirm bank details are linked; give the specific next payout date; if genuinely overdue, escalate with a 48-hour resolution timeline.
Pattern B (amount seems too low): explain MRP minus printing, platform commission and shipping; offer a line-by-line royalty breakdown; do not be defensive, offer transparency.""",
    "ISBN & Metadata Issues": "Treat as high priority; acknowledge it is a serious data issue; confirm immediate escalation to the production team; give a 48-hour resolution timeline.",
    "Printing & Quality": "Apologise sincerely; ask for photos of the defective copies; confirm a free reprint once verified; give a 5-7 business day timeline for the reprint.",
    "Distribution & Availability": "Explain it is typically a stock sync issue; confirm you are triggering a re-sync with the distribution team; set expectation of 24-48 hours.",
    "Book Status & Production Updates": "Use the actual production status; if delayed be honest about why (e.g. waiting for proof approval) without blaming the author; give a specific updated timeline.",
    "General Inquiry": "Answer directly and concisely (e.g. metadata updates via dashboard or email, reflecting in 3-5 business days).",
}


def knowledge_for(category: str | None) -> tuple[str, str]:
    key = category if category in SECTIONS else "General Inquiry"
    return f"{CORE}\n\n{SECTIONS[key]}", EXAMPLES[key]
