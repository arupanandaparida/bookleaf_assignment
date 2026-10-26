CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  name          TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('author','admin')),
  author_id     TEXT REFERENCES authors(author_id)
);

CREATE TABLE IF NOT EXISTS authors (
  author_id   TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  email       TEXT NOT NULL,
  phone       TEXT,
  city        TEXT,
  joined_date TEXT
);

CREATE TABLE IF NOT EXISTS books (
  book_id                  TEXT PRIMARY KEY,
  author_id                TEXT NOT NULL REFERENCES authors(author_id),
  title                    TEXT NOT NULL,
  isbn                     TEXT,
  genre                    TEXT,
  publication_date         TEXT,
  status                   TEXT NOT NULL,
  mrp                      INTEGER,
  author_royalty_per_copy  INTEGER,
  total_copies_sold        INTEGER NOT NULL DEFAULT 0,
  total_royalty_earned     INTEGER NOT NULL DEFAULT 0,
  royalty_paid             INTEGER NOT NULL DEFAULT 0,
  royalty_pending          INTEGER NOT NULL DEFAULT 0,
  last_royalty_payout_date TEXT,
  print_partner            TEXT,
  available_on             TEXT NOT NULL DEFAULT '[]'  -- JSON array
);
CREATE INDEX IF NOT EXISTS idx_books_author ON books(author_id);

CREATE TABLE IF NOT EXISTS tickets (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id        TEXT NOT NULL REFERENCES authors(author_id),
  book_id          TEXT REFERENCES books(book_id),   -- NULL = General / Account Level
  subject          TEXT NOT NULL,
  description      TEXT NOT NULL,
  attachments      TEXT NOT NULL DEFAULT '[]',        -- JSON [{name,size}] (metadata only)
  status           TEXT NOT NULL DEFAULT 'Open',
  category         TEXT,                              -- NULL until classified
  category_source  TEXT NOT NULL DEFAULT 'pending',   -- pending | ai | rules | admin
  priority         TEXT,
  priority_source  TEXT NOT NULL DEFAULT 'pending',
  ai_reasoning     TEXT,
  assigned_to      INTEGER REFERENCES users(id),
  ai_draft         TEXT,
  ai_draft_source  TEXT,                              -- ai | template
  ai_draft_at      TEXT,
  ai_draft_msgs    INTEGER,                           -- #messages when draft was made (staleness check)
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  first_response_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tickets_author ON tickets(author_id);
CREATE INDEX IF NOT EXISTS idx_tickets_queue  ON tickets(status, priority, created_at);

CREATE TABLE IF NOT EXISTS messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id   INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  sender_role TEXT NOT NULL CHECK (sender_role IN ('author','admin')),
  sender_id   INTEGER NOT NULL REFERENCES users(id),
  sender_name TEXT NOT NULL,
  body        TEXT NOT NULL,
  created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_ticket ON messages(ticket_id);

-- Internal notes live in their own table so they can never leak via the author message query.
CREATE TABLE IF NOT EXISTS notes (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id  INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  admin_id   INTEGER NOT NULL REFERENCES users(id),
  admin_name TEXT NOT NULL,
  body       TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_ticket ON notes(ticket_id);

-- Every LLM call is logged: powers cost visibility and debugging.
CREATE TABLE IF NOT EXISTS ai_calls (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id     INTEGER,
  kind          TEXT NOT NULL,       -- classify | draft
  model         TEXT,
  input_tokens  INTEGER DEFAULT 0,
  output_tokens INTEGER DEFAULT 0,
  latency_ms    INTEGER,
  ok            INTEGER NOT NULL,
  error         TEXT,
  created_at    TEXT NOT NULL
);
