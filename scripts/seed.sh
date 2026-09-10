#!/usr/bin/env bash
# Seed development/test data. Never targets production.
set -euo pipefail
: "${ENVIRONMENT:?ENVIRONMENT must be set}"
if [ "$ENVIRONMENT" = "prod" ]; then
  echo "seed: refusing to seed production" >&2
  exit 1
fi
echo "seed: no seed data yet (pass 1 scaffolding)"
