#!/usr/bin/env bash
# Store the demo's Token Factory key in Nebius MysteryBox as the secret "prime-demo-key", for --env-secret.
# The key is read with hidden input, checked against Token Factory before saving, and never written to a file
# or printed. Running it again replaces the stored value (a new primary version). Restart the endpoint after.
# Usage: scripts/store_demo_key.sh <project-id>
set -euo pipefail
PROJECT="${1:?usage: scripts/store_demo_key.sh <project-id>}"
NEBIUS="$(command -v nebius || echo "$HOME/.nebius/bin/nebius")"
BASE="${NEBIUS_BASE_URL:-https://api.tokenfactory.nebius.com/v1/}"

read -r -s -p "Paste the FULL prime-demo Token Factory key (hidden), then press Enter: " KEY; echo
KEY="$(printf '%s' "$KEY" | tr -d '[:space:]')"
[ -n "$KEY" ] || { echo "No key entered."; exit 1; }
CODE="$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $KEY" "${BASE%/}/models")"
if [ "$CODE" != "200" ]; then
    echo "Token Factory rejected that key (HTTP $CODE, ${#KEY} characters). Copy the whole key value, not its name or ID."
    exit 1
fi
echo "Token Factory accepted the key."
PAYLOAD="$(KEY="$KEY" python3 -c 'import json, os; print(json.dumps([{"key": "NEBIUS_API_KEY", "string_value": os.environ["KEY"]}]))')"
unset KEY

ID="$("$NEBIUS" mysterybox secret list --parent-id "$PROJECT" --format json | python3 -c '
import json, sys
print(next((s["metadata"]["id"] for s in json.load(sys.stdin).get("items", []) if s["metadata"]["name"] == "prime-demo-key"), ""))')"
if [ -n "$ID" ]; then
    "$NEBIUS" mysterybox secret-version create --parent-id "$ID" --payload "$PAYLOAD" --set-primary >/dev/null
    echo "Replaced the value of prime-demo-key."
else
    "$NEBIUS" mysterybox secret create --parent-id "$PROJECT" --name prime-demo-key \
        --description "Token Factory key for the Prime demo endpoint" --secret-version-payload "$PAYLOAD" >/dev/null
    echo "Saved the secret prime-demo-key in $PROJECT."
fi
unset PAYLOAD
