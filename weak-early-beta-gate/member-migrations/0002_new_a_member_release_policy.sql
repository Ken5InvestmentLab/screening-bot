CREATE TABLE new_a_member_release_policy (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  revision INTEGER NOT NULL CHECK (typeof(revision) = 'integer' AND revision BETWEEN 1 AND 9007199254740991),
  mode TEXT NOT NULL CHECK (mode IN ('off', 'canary', 'enabled')),
  source_commit TEXT NOT NULL CHECK (length(source_commit) = 40 AND source_commit NOT GLOB '*[^0-9a-f]*'),
  worker_version_id TEXT NOT NULL CHECK (
    length(worker_version_id) = 36
    AND substr(worker_version_id, 9, 1) = '-' AND substr(worker_version_id, 14, 1) = '-'
    AND substr(worker_version_id, 19, 1) = '-' AND substr(worker_version_id, 24, 1) = '-'
    AND length(replace(worker_version_id, '-', '')) = 32
    AND replace(worker_version_id, '-', '') NOT GLOB '*[^0-9a-f]*'
  ),
  canary_nonce TEXT,
  canary_subject_hmac TEXT,
  CHECK (
    (mode = 'canary'
      AND canary_nonce IS NOT NULL AND length(canary_nonce) = 64 AND canary_nonce NOT GLOB '*[^0-9a-f]*'
      AND canary_subject_hmac IS NOT NULL AND length(canary_subject_hmac) = 64
      AND canary_subject_hmac NOT GLOB '*[^0-9a-f]*')
    OR (mode IN ('off', 'enabled') AND canary_nonce IS NULL AND canary_subject_hmac IS NULL)
  )
);
