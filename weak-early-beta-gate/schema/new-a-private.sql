-- Additive new-A tables only. Never replace or migrate legacy preferences here.
CREATE TABLE IF NOT EXISTS new_a_private_datasets (
 dataset_id TEXT PRIMARY KEY,
 source_version TEXT NOT NULL,
 manifest_json TEXT NOT NULL,
 manifest_sha256 TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('STAGING','READY')),
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS new_a_private_parts (
 dataset_id TEXT NOT NULL,
 name TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 sha256 TEXT NOT NULL,
 byte_length INTEGER NOT NULL CHECK(byte_length BETWEEN 2 AND 196608),
 PRIMARY KEY(dataset_id,name),
 FOREIGN KEY(dataset_id) REFERENCES new_a_private_datasets(dataset_id)
);
CREATE TABLE IF NOT EXISTS new_a_active_pointer (
 pointer_key TEXT PRIMARY KEY CHECK(pointer_key='owner'),
 dataset_id TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(revision>0),
 updated_at TEXT NOT NULL,
 FOREIGN KEY(dataset_id) REFERENCES new_a_private_datasets(dataset_id)
);
CREATE TABLE IF NOT EXISTS new_a_finite_trial_preferences (
 member_id TEXT PRIMARY KEY,
 schema_version INTEGER NOT NULL CHECK(schema_version=1),
 preferences_json TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(revision>0),
 updated_at TEXT NOT NULL
);
