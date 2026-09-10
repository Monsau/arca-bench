#!/usr/bin/env bash
# Kubernetes probe script.
set -euo pipefail
PORT="${PORT:-8092}"
curl -fsS "http://localhost:${{PORT}}/healthz" > /dev/null
