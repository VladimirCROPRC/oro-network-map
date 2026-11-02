CREATE TABLE IF NOT EXISTS activity_admins (
  email TEXT PRIMARY KEY COLLATE NOCASE,
  can_manage_admins INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  created_by TEXT NOT NULL
);

INSERT OR IGNORE INTO activity_admins (email, can_manage_admins, created_by) VALUES
  ('felix.tibrea@proconect.ro', 1, 'system'),
  ('dorin.vlaic@proconect.ro', 0, 'system'),
  ('serban.mincic@proconect.ro', 0, 'system'),
  ('vladimir.carlan@proconect.ro', 0, 'system');
