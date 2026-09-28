#!/usr/bin/env bash
set -euo pipefail

for attempt in 1 2 3; do
  if python -m pip install --timeout 45 --retries 5 --only-binary=:all: -r requirements-actions.txt; then
    exit 0
  fi

  if [ "$attempt" -eq 3 ]; then
    echo "Python dependency installation failed after 3 attempts" >&2
    exit 1
  fi

  echo "Python dependency installation failed (attempt $attempt/3); retrying in 20 seconds" >&2
  sleep 20
done
