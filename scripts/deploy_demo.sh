#!/usr/bin/env bash
# Deploy the current commit to the live Nebius Serverless Endpoint, keeping its URL.
# Builds linux/amd64, pushes prime-demo:live (and :<commit>), restarts the endpoint, and waits until /health reports this commit.
# Needs Docker Desktop running and the Nebius CLI signed in. Usage: scripts/deploy_demo.sh
set -euo pipefail
export PATH="$HOME/.nebius/bin:$PATH"
cd "$(git rev-parse --show-toplevel)"
PROJECT="${PRIME_PROJECT:-project-u02xjhqwig00da3cbyybkn}"                    # us-north1
REPO="${PRIME_IMAGE_REPO:-cr.us-north1.nebius.cloud/u02pp4g5dpcfd2dh3x/prime-demo}"
NAME="${PRIME_ENDPOINT_NAME:-prime-demo}"

git diff --quiet && git diff --cached --quiet || { echo "Commit your changes first, so the live site matches a commit."; exit 1; }
VERSION="$(git rev-parse --short HEAD)"
docker version >/dev/null 2>&1 || { echo "Start Docker Desktop first."; exit 1; }

echo "Building $VERSION for linux/amd64 ..."
docker buildx build --platform linux/amd64 --build-arg PRIME_VERSION="$VERSION" \
    -t "${REPO}:live" -t "${REPO}:${VERSION}" --push . >/dev/null       # ${REPO}:live, not $REPO:live (zsh reads :l as a modifier)

ID="$(nebius ai endpoint get-by-name --parent-id "$PROJECT" --name "$NAME" --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["metadata"]["id"])')"
URL="$(nebius ai endpoint get "$ID" --format json | python3 -c '
import json, sys; e = json.load(sys.stdin)["status"].get("public_endpoints", [])
print(next(u for u in e if u.startswith("https://")))')"
echo "Restarting $NAME ($ID) ..."
nebius ai endpoint restart "$ID" >/dev/null

for _ in $(seq 1 90); do
    LIVE="$(curl -s -m 10 "$URL/health" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("version",""))' 2>/dev/null || true)"
    [ "$LIVE" = "$VERSION" ] && { echo "Live: $URL (version $VERSION)"; exit 0; }
    sleep 10
done
echo "The endpoint did not report version $VERSION within 15 minutes (it reports '${LIVE:-nothing}'). Check: nebius ai endpoint logs $ID"
exit 1
