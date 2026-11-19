CREATE TABLE new_a_member_observation_window_v1 (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  window_id TEXT NOT NULL UNIQUE CHECK (length(window_id) = 64 AND window_id NOT GLOB '*[^0-9a-f]*'),
  origin TEXT NOT NULL CHECK (origin IN (
    'https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev',
    'https://tentei-kyokuchi-cloud-member-stage.ipo-ken5-5489.workers.dev'
  )),
  source_commit TEXT NOT NULL CHECK (length(source_commit) = 40 AND source_commit NOT GLOB '*[^0-9a-f]*'),
  build_input_sha256 TEXT NOT NULL CHECK (length(build_input_sha256) = 64 AND build_input_sha256 NOT GLOB '*[^0-9a-f]*'),
  worker_version_id TEXT NOT NULL CHECK (length(worker_version_id) = 36),
  opens_at_ms INTEGER NOT NULL CHECK (typeof(opens_at_ms) = 'integer' AND opens_at_ms > 0),
  closes_at_ms INTEGER NOT NULL CHECK (
    typeof(closes_at_ms) = 'integer' AND closes_at_ms > opens_at_ms AND closes_at_ms - opens_at_ms <= 900000
  ),
  subject_key TEXT NOT NULL CHECK (length(subject_key) = 64 AND subject_key NOT GLOB '*[^0-9a-f]*'),
  allowed_subject_hmac TEXT NOT NULL CHECK (length(allowed_subject_hmac) = 64 AND allowed_subject_hmac NOT GLOB '*[^0-9a-f]*'),
  denied_subject_hmac TEXT NOT NULL CHECK (length(denied_subject_hmac) = 64 AND denied_subject_hmac NOT GLOB '*[^0-9a-f]*'),
  CHECK (allowed_subject_hmac <> denied_subject_hmac)
);

CREATE TABLE new_a_member_response_observation_v1 (
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
      AND ((role_result = 'allowed' AND status = 200) OR (role_result = 'denied' AND status = 403)))
    OR (route = '/api/cloud/new-a-finite/input/manifest.json' AND status = 403 AND role_result = 'not_checked')
  )
);
