#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXAMPLE="$ROOT/env.example"
ENV_FILE="$ROOT/.env"

if [[ ! -f "$EXAMPLE" ]]; then
  echo "env.example not found at $EXAMPLE" >&2
  exit 1
fi

if [[ -f "$ENV_FILE" ]]; then
  echo ".env already exists at $ENV_FILE"
  echo "Edit KIS_APP_KEY, KIS_APP_SECRET, ACCOUNT_NO, ANTHROPIC_API_KEY before smoke tests."
  exit 0
fi

cp "$EXAMPLE" "$ENV_FILE"
echo "Created $ENV_FILE from env.example"
echo "Next: edit .env with your KIS mock-trading keys and Anthropic API key."
