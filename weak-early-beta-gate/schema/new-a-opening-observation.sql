-- Supplemental private schema. The browser has no write route.
CREATE TABLE IF NOT EXISTS new_a_opening_observations (
 member_id TEXT NOT NULL CHECK(length(member_id)=70 AND substr(member_id,1,6)='cloud_' AND substr(member_id,7) NOT GLOB '*[^0-9a-f]*'),
 target_date TEXT NOT NULL CHECK(length(target_date)=10),
 dataset_id TEXT NOT NULL,
 pointer_revision INTEGER NOT NULL CHECK(pointer_revision>0),
 manifest_sha256 TEXT NOT NULL CHECK(length(manifest_sha256)=64 AND manifest_sha256 NOT GLOB '*[^0-9a-f]*'),
 preferences_revision INTEGER NOT NULL CHECK(preferences_revision>0),
 revision INTEGER NOT NULL CHECK(revision>0),
 updated_at TEXT NOT NULL CHECK(length(updated_at)=24),
 source_receipt_sha256 TEXT NOT NULL CHECK(length(source_receipt_sha256)=64 AND source_receipt_sha256 NOT GLOB '*[^0-9a-f]*'),
 rows_json TEXT NOT NULL CHECK(json_valid(rows_json) AND length(CAST(rows_json AS BLOB)) BETWEEN 2 AND 98304),
 rows_sha256 TEXT NOT NULL CHECK(length(rows_sha256)=64 AND rows_sha256 NOT GLOB '*[^0-9a-f]*'),
 PRIMARY KEY(member_id,target_date,dataset_id,pointer_revision,manifest_sha256,preferences_revision),
 FOREIGN KEY(dataset_id) REFERENCES new_a_private_datasets(dataset_id)
);
