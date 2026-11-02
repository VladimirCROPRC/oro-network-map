CREATE TABLE IF NOT EXISTS activity_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  viewed_at TEXT NOT NULL DEFAULT (datetime('now')),
  email TEXT NOT NULL,
  event_type TEXT NOT NULL DEFAULT 'view',
  layer_id TEXT,
  layer_name TEXT,
  element_id TEXT,
  element_name TEXT
);

CREATE INDEX IF NOT EXISTS idx_activity_viewed_at
  ON activity_logs(viewed_at DESC);

CREATE INDEX IF NOT EXISTS idx_activity_email_viewed_at
  ON activity_logs(email, viewed_at DESC);
