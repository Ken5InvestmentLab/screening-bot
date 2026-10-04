-- LOCAL first. Does not create/bind a production database or enable delivery.
CREATE TABLE IF NOT EXISTS cloud_push_subscription_metadata (
  subscription_id TEXT PRIMARY KEY REFERENCES cloud_push_subscriptions(subscription_id),
  endpoint_hash TEXT NOT NULL,
  vapid_public_key TEXT NOT NULL,
  expires_at_ms INTEGER,
  registered_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cloud_push_dispatch_receipts (
  member_id TEXT NOT NULL,
  subscription_id TEXT NOT NULL,
  event_key TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('preparing', 'held', 'accepted', 'rejected', 'unknown', 'expired')),
  reason TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (member_id, subscription_id, event_key)
);
