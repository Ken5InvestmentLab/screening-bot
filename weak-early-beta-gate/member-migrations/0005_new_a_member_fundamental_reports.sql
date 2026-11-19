-- Premium-only reports referenced by the immutable history part for this generation.
CREATE TABLE private_projection_fundamental (
  identity TEXT NOT NULL REFERENCES private_projection_manifest(identity),
  sha256 TEXT NOT NULL CHECK (length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
  json TEXT NOT NULL CHECK (json_valid(json) AND length(CAST(json AS BLOB)) BETWEEN 1 AND 16384),
  PRIMARY KEY (identity, sha256)
);
