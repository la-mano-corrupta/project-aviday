-- 1. Live Owner Status & Control Center State (Single-row table id = 1)
CREATE TABLE IF NOT EXISTS owner_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  status_mode TEXT DEFAULT 'online',          -- 'online', 'sleeping', 'busy'
  status_message TEXT DEFAULT 'Available',    -- e.g. 'Sleeping', 'At the gym'
  started_at INTEGER DEFAULT NULL,            -- Unix timestamp in ms when status started
  available_at INTEGER DEFAULT NULL,          -- Unix timestamp in ms when owner will be back online
  last_loml_alert_at INTEGER DEFAULT 0,       -- Cooldown tracker so admin gets alerted cleanly when VIP texts
  extra_notes TEXT DEFAULT ''                 -- Dynamic facts added via Admin Control Center DMs
);

INSERT OR IGNORE INTO owner_state (id, status_mode, status_message)
VALUES (1, 'online', 'Online and available');

-- 2. Permanent Memory Per Instagram User
CREATE TABLE IF NOT EXISTS user_memories (
  ig_user_id TEXT PRIMARY KEY,
  username TEXT DEFAULT '',
  memory_summary TEXT DEFAULT '',             -- Permanent facts remembered about this person
  is_paused INTEGER DEFAULT 0,                -- 1 if owner took over conversation manually
  updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
);

-- 3. Short-Term Conversation History (Last N messages per user)
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ig_user_id TEXT NOT NULL,
  role TEXT NOT NULL,                         -- 'user' or 'assistant'
  content TEXT NOT NULL,
  created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
);

CREATE INDEX IF NOT EXISTS idx_messages_user_time ON messages(ig_user_id, created_at DESC);
