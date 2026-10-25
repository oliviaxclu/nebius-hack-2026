#!/usr/bin/env bash
# Publish the current commit to a Hugging Face Docker Space as the hosted demo.
# Uses the Hugging Face CLI login (`hf auth login`, browser sign-in is fine), so no git token is needed.
# The Space needs a settings header at the top of its README; it is added only to the uploaded copy,
# so the GitHub README stays clean. Usage: scripts/push_space.sh <hf-username>/<space-name>
set -euo pipefail
SPACE="${1:?usage: scripts/push_space.sh <hf-username>/<space-name>}"
cd "$(git rev-parse --show-toplevel)"
HF="$(command -v hf || echo .venv/bin/hf)"
[ -x "$HF" ] || { echo "Install the Hugging Face CLI first: .venv/bin/pip install huggingface_hub"; exit 1; }
git diff --quiet && git diff --cached --quiet || { echo "Commit or stash your changes first."; exit 1; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
git archive HEAD | tar -x -C "$TMP"                  # exactly the committed files: no .env, no local data
{ cat <<'YAML'
---
title: Prime
emoji: 💉
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 8080
pinned: false
license: mit
short_description: Accessible glucose explainer and pen check on Nemotron
---

YAML
  cat "$TMP/README.md"; } > "$TMP/README.space.md" && mv "$TMP/README.space.md" "$TMP/README.md"

"$HF" upload "$SPACE" "$TMP" . --repo-type space --delete "*" \
    --commit-message "Deploy $(git rev-parse --short HEAD)"
echo "Uploaded. Watch the build at https://huggingface.co/spaces/${SPACE} (Logs), then open https://${SPACE/\//-}.hf.space"
