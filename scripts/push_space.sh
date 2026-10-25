#!/usr/bin/env bash
# Push the current commit to a Hugging Face Docker Space as the hosted demo.
# The Space needs a settings header at the top of its README; it is added only to the pushed copy,
# so the GitHub README stays clean. Usage: scripts/push_space.sh <hf-username>/<space-name>
set -euo pipefail
SPACE="${1:?usage: scripts/push_space.sh <hf-username>/<space-name>}"
REMOTE="${SPACE_REMOTE:-https://huggingface.co/spaces/${SPACE}}"   # SPACE_REMOTE: for testing against a local repo
git diff --quiet && git diff --cached --quiet || { echo "Commit or stash your changes first."; exit 1; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
git worktree add --detach "$TMP/space" HEAD >/dev/null
cd "$TMP/space"
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
  cat README.md; } > README.space.md && mv README.space.md README.md
git add README.md
git -c user.name="$(git -C "$OLDPWD" config user.name)" -c user.email="$(git -C "$OLDPWD" config user.email)" \
    commit -q -m "Hugging Face Space settings for $(git rev-parse --short HEAD~0)"
git push --force "$REMOTE" HEAD:main
cd - >/dev/null && git worktree remove --force "$TMP/space"
echo "Pushed. Watch the build at $REMOTE (Logs), then open https://${SPACE/\//-}.hf.space"
