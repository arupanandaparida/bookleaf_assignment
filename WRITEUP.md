# Write-up: Author Support & Communication Portal

**Stack.** Python/FastAPI backend (async endpoints, pydantic validation, auto-generated OpenAPI docs), SQLite, and a React client served by the same process.

**What I prioritised.** The brief weights AI integration and architecture highest, so I built the core ticket loop end to end first (author submits → AI classifies and scores → admin gets a grounded draft → reply appears live on the author's screen), then hardened it, then added the UI polish. Everything is covered by integration tests.

**AI approach.** Two small, separate calls instead of one big one: a cheap deterministic classify+priority call (JSON, validated) when a ticket arrives, and a lazily generated, cached draft when an admin opens it. The draft prompt is built from three things: BookLeaf's tone rules, *only* the Knowledge Base section for the ticket's category, and **facts computed from the database** (copies × royalty, paid/pending, ₹1,000 threshold, the real next payout deadline, production stage). That is what makes a reply say "your ₹2,546 is above the threshold, and the Q3 payout is due by 14 November" rather than generic reassurance. The prompt also states what the model cannot know (bank-link status, tracking) so it commits to a verification timeline instead of inventing facts.

**Trade-offs.**
- *FastAPI + SQLite and in-process SSE* over Postgres and Redis: zero setup and fully testable, at the cost of a single-instance deployment.
- *Rule-based fallbacks* cost extra code, but a support tool that stops working when an API is rate-limited is worse than one that gets less clever. Tickets are never blocked on AI and an admin can always type a reply.
- *Lazy drafting* means the admin waits a couple of seconds on first open, but we never pay to draft tickets nobody opens.
- *No auto-send.* AI output is always a draft a human reviews. At this stage the cost of a wrong royalty promise outweighs the saving.
- Attachments are UI-only, as allowed by the brief.

**Taking it to production.**
1. Postgres + Redis (pub/sub, rate limits, job queue so classification retries survive restarts); object storage for attachments; email notifications on replies.
2. **Measure quality:** log admin overrides (AI vs final category/priority) and draft edit distance; use them as an eval set to tune prompts and decide when to cheapen or upgrade the model. Add thumbs up/down on drafts.
3. Retrieval over a larger, versioned knowledge base (embeddings) once policies outgrow a prompt; Anthropic prompt caching for the stable prefix.
4. Pull real royalty line-items and bank-link status from the finance system so drafts can answer "why is my royalty low" with an actual breakdown.
5. SSO for staff, audit log, SLA timers and auto-escalation for Critical tickets, and PII redaction before text is sent to the model.
