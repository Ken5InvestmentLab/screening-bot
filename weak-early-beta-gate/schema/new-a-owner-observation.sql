-- Draft only: no deploy or execution against a remote database.
CREATE TABLE IF NOT EXISTS new_a_protected_owner_observations_v1 (
  worker TEXT NOT NULL CHECK(worker='tentei-kyokuchi-cloud'),
  version_id TEXT NOT NULL CHECK(length(version_id)=36),
  build_input_sha256 TEXT NOT NULL CHECK(length(build_input_sha256)=64),
  source_commit TEXT NOT NULL CHECK(length(source_commit)=40),
  version_timestamp TEXT NOT NULL CHECK(length(version_timestamp) BETWEEN 20 AND 30),
  route TEXT NOT NULL CHECK(route IN ('/weak_early_beta_latest.html','/api/cloud/new-a-finite/access')),
  observed_at_ms INTEGER NOT NULL CHECK(observed_at_ms>0),
  observed_slot INTEGER NOT NULL CHECK(observed_slot=CAST(observed_at_ms / 300000 AS INTEGER)),
  status INTEGER NOT NULL CHECK(status=200),
  strategy TEXT NOT NULL CHECK(strategy='A_BASE'),
  api_contract_verified INTEGER NOT NULL CHECK(api_contract_verified=CASE WHEN route='/api/cloud/new-a-finite/access' THEN 1 ELSE 0 END),
  PRIMARY KEY (worker,version_id,route,observed_slot)
);
CREATE TRIGGER IF NOT EXISTS new_a_owner_observations_v1_no_update
BEFORE UPDATE ON new_a_protected_owner_observations_v1
BEGIN SELECT RAISE(ABORT,'observations_append_only'); END;
CREATE TRIGGER IF NOT EXISTS new_a_owner_observations_v1_no_delete
BEFORE DELETE ON new_a_protected_owner_observations_v1
BEGIN SELECT RAISE(ABORT,'observations_append_only'); END;
