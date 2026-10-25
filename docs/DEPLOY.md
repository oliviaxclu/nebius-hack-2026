# Deploying the public demo on Nebius Serverless Endpoints

The judge-facing demo is a CPU-only container serving **only the synthetic patient**; each visitor gets a private in-memory copy of the database, and inference goes to Nemotron on Nebius Token Factory.

Legend: OK = from Nebius docs/cookbook; CHECK = not verified here, confirm before relying on it.

## 0. Run locally first
```bash
pip install -e ".[dev]" && cp .env.example .env     # add NEBIUS_API_KEY
python -m uvicorn prime.web:create_app --factory --port 8080
```
## 1. A dedicated, capped key
Create a **separate Token Factory API key for the demo** and delete it after judging. In-app caps: `DEMO_MAX_CALLS_PER_SESSION` (25) and `DEMO_MAX_CALLS_PER_DAY` (500). A question runs the agent loop (several model calls), so size the daily cap against your credit.
## 2. Build and push (to Nebius Container Registry)
Serverless Endpoints run linux/amd64. On an Apple Silicon Mac, build for that platform explicitly, or the endpoint will not start.
```bash
export REGION_ID=eu-north1                                                     # CHECK: your project's region
export REGISTRY_PATH=$(nebius registry create --name prime --format json | jq -r ".metadata.id" | cut -d- -f 2)
nebius registry configure-helper                                               # lets docker push to cr.<region>.nebius.cloud
export IMAGE=cr.$REGION_ID.nebius.cloud/$REGISTRY_PATH/prime-demo:0.3
docker buildx build --platform linux/amd64 -t $IMAGE --push .                  # the image contains no secrets
```
(Docker Hub also works: `docker buildx build --platform linux/amd64 -t <user>/prime-demo:0.3 --push .`)
## 3. Create the endpoint (what worked, 2026-10-25)
OK, tested: Nebius AI Cloud needs payment details on the account before it lets you create anything (Token Factory credits do not
cover AI Cloud). Pick a region where your CPU quota is above 0 (`nebius quotas quota-allowance list --parent-id <tenant-id>`;
here eu-north1 and us-central1 were 0, us-north1 was 200).
```bash
export PATH="$HOME/.nebius/bin:$PATH" P=<project-id>                           # the CLI's docker helper lives in ~/.nebius/bin
scripts/store_demo_key.sh $P                                                   # hidden input; checks the key with Token Factory first
nebius mysterybox secret get <secret-id> --format json | jq -r .spec.primary_version_id     # the version to pin
nebius ai endpoint create --parent-id $P --name prime-demo --image "$IMAGE" \
  --platform cpu-d3 --preset 2vcpu-8gb --container-port 8080 --auth none \
  --env DEMO_MAX_CALLS_PER_DAY=300 --env-secret NEBIUS_API_KEY=<secret-id>@<version-id>
```
- Name the CPU platform: the default platform is an H100 GPU. The `https://` URL is provided automatically; `--public` only adds a public IP.
- `--auth none` so judges can open it in a browser. `/health` shows `key_configured`.
- The endpoint pins the secret version it was created with, and the CLI has no `update`: to change the key, store it again,
  then delete and recreate the endpoint with the new version (the URL changes).
## 3b. Optional: speech to text with Nemotron 3 Nano Omni
Without this, voice uses the browser's speech recognition (Chrome sends that audio to Google). With it, audio goes only to your Omni endpoint and is not stored.

OK (tested 2026-10-25): the public Token Factory API accepts only text, image and video content and has no `/audio/transcriptions` route, so no public model takes audio.
Two ways to get Omni:
- **A. Token Factory dedicated endpoint** (simplest if your account offers it): Nebius lists Nemotron-3-Nano-Omni as *dedicated only*. Create it in the Token Factory console; Prime then needs only `PRIME_SPEECH_MODEL=<the id it shows>` (plus `PRIME_SPEECH_BASE_URL` if it differs). CHECK the id and URL in the console.
- **B. Nebius Serverless Endpoint running vLLM** (you run the model yourself): steps below, adapted from the vLLM-on-Nebius guide (docs.vllm.ai, deployment/frameworks/nebius).

### B. Serverless Endpoint with vLLM
GPU sizing from the model card: FP8 needs at least 1x L40S 48 GB; BF16 needs 1x H100 80 GB.
```bash
export PROJECT_ID="<project-id>" SUBNET_ID="<subnet-id>"
export MODEL_ID="nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-FP8"      # or ...-BF16 on gpu-h100-sxm / 1gpu-16vcpu-200gb
export AUTH_TOKEN="$(openssl rand -hex 32)"                              # this endpoint's own token, not your Token Factory key
export VLLM_IMAGE="vllm/vllm-openai:<version>"                           # CHECK: a release that supports Nemotron 3 Nano Omni; pin it
nebius ai endpoint create \
  --parent-id "$PROJECT_ID" --subnet-id "$SUBNET_ID" \
  --name prime-omni \
  --image "$VLLM_IMAGE" \
  --container-command vllm \
  --args "serve $MODEL_ID --host 0.0.0.0 --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.9" \
  --platform gpu-l40s-a --preset 1gpu-8vcpu-32gb \
  --container-port 8000/http \
  --auth token --token "$AUTH_TOKEN" \
  --disk-size 250Gi --shm-size 16Gi \
  --public=false --preemptible=false
```
- `--args` is split on spaces, so keep it to plain flags (no quotes inside).
- CHECK: the model card says audio needs `vllm[audio]` in the container. If audio requests fail with a missing-library error, build a small image `FROM` the vLLM image that runs `pip install "vllm[audio]"` at the same version, and use that as `--image`.
- CHECK: the 32 GB RAM preset is the guide's example for a small model; if loading the 33 GB FP8 weights fails, pick a preset with more memory (`nebius compute platform list --parent-id "$PROJECT_ID"`).
- First start downloads the weights (tens of GB), so `STARTING` can take a while; the URL may 404 until `RUNNING`.

Get the URL and check it:
```bash
export ENDPOINT_ID="$(nebius ai endpoint get-by-name --parent-id "$PROJECT_ID" --name prime-omni --format jsonpath='{.metadata.id}')"
export ENDPOINT_URL="$(nebius ai endpoint get "$ENDPOINT_ID" --format json | jq -er '[.status.public_endpoints[]? | select(startswith("https://"))][0]')"
curl -sS "$ENDPOINT_URL/health" -H "Authorization: Bearer $AUTH_TOKEN"
curl -sS "$ENDPOINT_URL/v1/models" -H "Authorization: Bearer $AUTH_TOKEN"      # should list $MODEL_ID
```

### Test transcription with real speech (either option)
```bash
say -o q.wav --data-format=LEI16@16000 "Why were my mornings so high last week?"
PRIME_SPEECH_BASE_URL="$ENDPOINT_URL/v1" PRIME_SPEECH_API_KEY="$AUTH_TOKEN" PRIME_SPEECH_MODEL="$MODEL_ID" python - <<'PY'
import base64, os
from openai import OpenAI
c = OpenAI(base_url=os.environ["PRIME_SPEECH_BASE_URL"], api_key=os.environ["PRIME_SPEECH_API_KEY"])
url = "data:audio/wav;base64," + base64.b64encode(open("q.wav", "rb").read()).decode()
r = c.chat.completions.create(model=os.environ["PRIME_SPEECH_MODEL"], temperature=0,
    messages=[{"role": "user", "content": [{"type": "audio_url", "audio_url": {"url": url}}, {"type": "text", "text": "Transcribe this audio."}]}],
    extra_body={"chat_template_kwargs": {"enable_thinking": False}})
print(r.choices[0].message.content)
PY
```
For option A, use your Token Factory base URL and key instead of `$ENDPOINT_URL/v1` and `$AUTH_TOKEN`.

### Point Prime at it
```bash
PRIME_SPEECH_MODEL="$MODEL_ID" PRIME_SPEECH_BASE_URL="$ENDPOINT_URL/v1" PRIME_SPEECH_API_KEY="$AUTH_TOKEN" \
  PRIME_HOME=./.prime-data .venv/bin/python -m uvicorn prime.web:create_app --factory --port 8080
curl -s localhost:8080/health                                              # "speech": true
```
Open http://localhost:8080 in Chrome, tap **Talk**, ask a question, and check that Settings shows *Speech to text: Nemotron Omni on Nebius* and **Privacy** lists a *Voice clip*.

GPU endpoints bill per hour while running. Stop it when you are not testing; stopping keeps the endpoint (and its URL) for later:
```bash
nebius ai endpoint stop "$ENDPOINT_ID"
nebius ai endpoint get "$ENDPOINT_ID" --format jsonpath='{.status.state}'   # wait for STOPPED before starting again
nebius ai endpoint start "$ENDPOINT_ID"                                      # resume; wait for RUNNING
nebius ai endpoint delete "$ENDPOINT_ID"                                     # after judging: removes it and its URL
```
Or in the console: Serverless AI > Endpoints > the endpoint's menu > Stop. CHECK the `jsonpath` field name with `nebius ai endpoint get "$ENDPOINT_ID" --format json`.

## 4. URL and smoke test
```bash
ID=$(nebius ai endpoint get-by-name --name prime-demo --format jsonpath='{.metadata.id}')
nebius ai endpoint get "$ID" --format jsonpath='{.status.public_endpoints[0]}'
nebius ai endpoint logs "$ID" --tail 100 --timestamps
```
Wait for RUNNING (the address can 404 while STARTING). CHECK whether the address is http-only or HTTPS; browsers need HTTPS for speech recognition. Smoke test: `curl <url>/health`, open `<url>/`, run the pen check, click a starter, confirm the "Sent to the model" panel fills in.
## 5. Keep it up through judging
Endpoints bill until stopped. Estimate the cost for the whole judging window, put the URL and "no login needed" in the Devpost testing instructions, and delete the endpoint and the demo key afterward.
