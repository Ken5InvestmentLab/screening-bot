ALTER TABLE new_a_member_release_policy ADD COLUMN canary_free_subject_hmac TEXT CHECK (
  canary_free_subject_hmac IS NULL OR (
    mode = 'canary' AND length(canary_free_subject_hmac) = 64
    AND canary_free_subject_hmac NOT GLOB '*[^0-9a-f]*'
    AND canary_free_subject_hmac <> canary_subject_hmac
  )
);

CREATE TABLE new_a_member_response_observation_v2 (
  window_id TEXT NOT NULL CHECK (length(window_id) = 64),
  origin TEXT NOT NULL,
  source_commit TEXT NOT NULL CHECK (length(source_commit) = 40),
  build_input_sha256 TEXT NOT NULL CHECK (length(build_input_sha256) = 64),
  worker_version_id TEXT NOT NULL CHECK (length(worker_version_id) = 36),
  subject_hmac TEXT NOT NULL CHECK (length(subject_hmac) = 64 AND subject_hmac NOT GLOB '*[^0-9a-f]*'),
  route TEXT NOT NULL,
  status INTEGER NOT NULL,
  role_result TEXT NOT NULL,
  observed_at_ms INTEGER NOT NULL CHECK (typeof(observed_at_ms) = 'integer' AND observed_at_ms > 0),
  PRIMARY KEY (window_id, subject_hmac, route),
  CHECK (
    (route IN ('/weak_early_beta_latest.html', '/api/cloud/new-a-view/history.json')
      AND status = 200 AND role_result IN ('allowed', 'denied'))
    OR (route = '/api/cloud/new-a-view/dashboard.json'
      AND ((status = 200 AND role_result = 'allowed') OR (status = 403 AND role_result = 'denied')))
    OR (route = '/api/cloud/new-a-finite/input/manifest.json' AND status = 403 AND role_result = 'not_checked')
  )
);
