-- Private handoff from the verified New A publisher to the owner-only Worker.
-- The staged candidate is separate from the legacy notification ledger.
CREATE TABLE IF NOT EXISTS new_a_owner_notice_queue (
 target_date TEXT NOT NULL CHECK(length(target_date)=10),
 kind TEXT NOT NULL CHECK(kind IN ('WATCH_TO_SIMULATED_HOLDING','EVALUATION_DAY_MORNING')),
 payload_json TEXT NOT NULL CHECK(json_valid(payload_json) AND length(CAST(payload_json AS BLOB)) BETWEEN 2 AND 90112),
 payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64 AND payload_sha256 NOT GLOB '*[^0-9a-f]*'),
 PRIMARY KEY(target_date,kind)
);
