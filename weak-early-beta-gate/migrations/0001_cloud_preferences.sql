-- Apply to a LOCAL test D1 database first. No database/binding is created by code.
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS cloud_member_links (
  member_id TEXT PRIMARY KEY,
  discord_user_id TEXT NOT NULL UNIQUE,
  whop_user_id TEXT NOT NULL UNIQUE,
  membership_id TEXT NOT NULL,
  payment_id TEXT NOT NULL,
  environment TEXT NOT NULL CHECK (environment IN ('live', 'test')),
  verification_method TEXT NOT NULL CHECK (verification_method IN ('dual_oauth', 'verified_operator')),
  evidence_reference TEXT NOT NULL CHECK (length(evidence_reference) > 0),
  verified_at TEXT NOT NULL,
  revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS cloud_member_preferences (
  member_id TEXT PRIMARY KEY,
  preferences_json TEXT NOT NULL CHECK (json_valid(preferences_json)),
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cloud_push_subscriptions (
  subscription_id TEXT PRIMARY KEY,
  member_id TEXT NOT NULL,
  endpoint TEXT NOT NULL UNIQUE,
  p256dh TEXT NOT NULL,
  auth TEXT NOT NULL,
  opted_in_at TEXT NOT NULL,
  revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS cloud_push_subscriptions_member ON cloud_push_subscriptions(member_id);
CREATE TABLE IF NOT EXISTS cloud_notification_events (
  source_event_key TEXT PRIMARY KEY,
  event_json TEXT NOT NULL CHECK (json_valid(event_json)),
  available_at TEXT NOT NULL,
  source_ledger_revision TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cloud_notification_deliveries (
  member_id TEXT NOT NULL,
  event_key TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('dry_run_eligible', 'suppressed', 'held', 'sent')),
  reason TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  membership_checked_at TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (member_id, event_key)
);
CREATE TABLE IF NOT EXISTS cloud_whop_webhook_receipts (
  webhook_id TEXT PRIMARY KEY,
  api_version TEXT NOT NULL,
  api_version_date TEXT NOT NULL,
  received_at TEXT NOT NULL,
  reconciled_at TEXT
);
