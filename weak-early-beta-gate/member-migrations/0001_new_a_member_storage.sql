CREATE TABLE private_projection_manifest (
  identity TEXT PRIMARY KEY NOT NULL,
  digest TEXT UNIQUE NOT NULL CHECK (length(digest) = 64),
  json TEXT NOT NULL CHECK (json_valid(json))
);

CREATE TABLE private_projection_part (
  identity TEXT NOT NULL REFERENCES private_projection_manifest(identity),
  kind TEXT NOT NULL CHECK (kind IN ('history', 'analytics', 'chart')),
  idx INTEGER NOT NULL CHECK (idx >= 0),
  json TEXT NOT NULL CHECK (json_valid(json)),
  PRIMARY KEY (identity, kind, idx)
);

CREATE TABLE private_projection_ready (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  identity TEXT NOT NULL REFERENCES private_projection_manifest(identity),
  digest TEXT NOT NULL CHECK (length(digest) = 64)
);

CREATE TABLE new_a_member_settings (
  scope TEXT PRIMARY KEY NOT NULL CHECK (length(scope) = 64),
  revision INTEGER NOT NULL CHECK (revision >= 1),
  trial_json TEXT NOT NULL CHECK (json_valid(trial_json)),
  view_json TEXT NOT NULL CHECK (json_valid(view_json)),
  requested_at TEXT NOT NULL
);

CREATE TABLE new_a_member_results (
  scope TEXT PRIMARY KEY NOT NULL REFERENCES new_a_member_settings(scope),
  settings_revision INTEGER NOT NULL CHECK (settings_revision >= 1),
  dataset_id TEXT NOT NULL,
  dataset_revision INTEGER NOT NULL CHECK (dataset_revision >= 1),
  as_of TEXT NOT NULL,
  source_version TEXT NOT NULL CHECK (length(source_version) = 64),
  metrics_json TEXT NOT NULL CHECK (json_valid(metrics_json))
);
