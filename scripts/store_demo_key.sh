#!/usr/bin/env bash
# Store the demo's Token Factory key in Nebius MysteryBox as the secret "prime-demo-key", for --env-secret.
# The key is read with hidden input and never written to a file or printed.
# Usage: scripts/store_demo_key.sh <project-id>
set -euo pipefail
PROJECT="${1:?usage: scripts/store_demo_key.sh <project-id>}"
NEBIUS="$(command -v nebius || echo "$HOME/.nebius/bin/nebius")"
read -r -s -p "Paste the prime-demo Token Factory key (hidden), then press Enter: " KEY; echo
[ -n "$KEY" ] || { echo "No key entered."; exit 1; }
PAYLOAD="$(KEY="$KEY" python3 -c 'import json, os; print(json.dumps([{"key": "NEBIUS_API_KEY", "string_value": os.environ["KEY"]}]))')"
unset KEY
"$NEBIUS" mysterybox secret create --parent-id "$PROJECT" --name prime-demo-key \
    --description "Token Factory key for the Prime demo endpoint" --secret-version-payload "$PAYLOAD" >/dev/null
unset PAYLOAD
echo "Saved the secret prime-demo-key in $PROJECT."
