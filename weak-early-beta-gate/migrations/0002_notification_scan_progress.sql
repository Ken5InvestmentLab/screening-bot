-- Local migration test only in this revision; production application is separate.
-- This is additive: delivery states and existing candidate IDs are unchanged.
CREATE TABLE IF NOT EXISTS cloud_notification_scan_progress (
  member_id TEXT PRIMARY KEY,
  after_available_at TEXT NOT NULL DEFAULT '',
  after_source_event_key TEXT NOT NULL DEFAULT '',
  cycle_cutoff_at TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS cloud_notification_events_scan
  ON cloud_notification_events(available_at, source_event_key);
