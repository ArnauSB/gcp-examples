# Serverless CI/CD & Canary Deployments on Google Cloud

This directory contains a complete Infrastructure as Code (IaC) and CI/CD example for deploying a Python FastAPI application to Google Cloud Run using a progressive canary release strategy (`10% → 50% → 100%` with inline health checks).

## Architecture Overview

This demo leverages the following Google Cloud Platform services:

* **Cloud Run:** Serverless compute platform to run the API container.
* **Cloud Build:** Serverless CI/CD platform that builds, scans, deploys, and progressively promotes each revision in a single pipeline.
* **Artifact Registry:** Secure private repository to store the built Docker images.
* **Container Scanning / Container Analysis:** Automatically scans every image pushed to Artifact Registry for OS-package CVEs; the pipeline reads the findings and gates the deploy.
* **Cloud IAM:** Least-privilege service accounts to securely execute the pipeline.
* **Terraform:** Provisions the foundational infrastructure and wires the GitHub trigger.

### The Pipeline Flow
1. A push to the `main` branch triggers Google Cloud Build.
2. Cloud Build builds the Docker image and pushes it to Artifact Registry.
3. Artifact Registry scans the image; Cloud Build polls the Container Analysis API and **fails the build** if any finding matches the configured severity threshold (default `CRITICAL`).
4. Cloud Build deploys the new revision to Cloud Run with `--no-traffic --tag=canary`, giving it a stable URL (`https://canary---my-api-service-<hash>.<region>.run.app`) without exposing it to real users yet.
5. Cloud Build smoke-tests the canary by hitting its tagged URL's `/health` endpoint. If the smoke test fails, the build aborts before any traffic is shifted.
6. Cloud Build runs a **progressive ramp**: `10%` → bake 2 min (sampling the canary URL for 5xx) → `50%` → bake 2 min → `100%`. If 5xx responses during any bake window exceed the tolerance, Cloud Build reverts traffic to the previous stable revision and fails the build.
7. At `100%`, Cloud Build drops the canary tag — the revision graduates to the new stable.

---

## Prerequisites

Before running this example, ensure you have:
1. A Google Cloud Project with billing enabled.
2. The [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (`gcloud`) installed and authenticated (`gcloud auth application-default login`).
3. [Terraform](https://developer.hashicorp.com/terraform/downloads) installed locally.
4. The [Google Cloud Build GitHub App](https://github.com/marketplace/google-cloud-build) connected to your GCP project.

---

## 🚀 How to Run the Demo

### 1. Provision the Infrastructure
Navigate to the `infra/` directory and use Terraform to create the required GCP resources (APIs, Service Account, Artifact Registry, and the Cloud Build Trigger).

```bash
cd deploy-to-cloud-run/infra/
terraform init
terraform apply
```

### 2. Run the V1 → V4 walkthrough

`terraform apply` provisions the Cloud Run service with a `cloudrun/container/hello` placeholder revision at `100%`. Every subsequent push is treated as a canary against the current stable — no V1-specific editing of `cloudbuild.yaml` is needed.

#### V1 — the first real release
1. No code changes required; just push the repo as-is. The pipeline:
   - Builds + scans the FastAPI image
   - Smoke-tests `/health` on the V1 canary URL
   - Ramps `10% → 50% → 100%` against the `hello` placeholder
   - V1 graduates as the new stable; placeholder is gone

#### V2 — a successful canary
1. Make a visible change to the app (e.g. update the `message` field in [app/main.py](deploy-to-cloud-run/app/main.py)).
2. Commit and push.
3. Watch the ramp: open Cloud Build logs for the new build — you'll see the `===== Stage 1: 10% canary =====`, `===== Stage 2: 50% =====`, `===== Stage 3: 100% =====` markers separated by 2-minute bake windows.

In a second terminal, watch the traffic split live:
```bash
watch -n 5 'gcloud run services describe my-api-service \
  --region=europe-west1 --format=json \
  | jq ".status.traffic"'
```

And in a third, generate user-side traffic to see the canary mix in:
```bash
URL=$(gcloud run services describe my-api-service --region=europe-west1 --format='value(status.url)')
while true; do curl -s "$URL"; echo; sleep 0.5; done
```

#### V3 — a broken canary (rollback)
1. Edit [app/main.py](deploy-to-cloud-run/app/main.py) so the root endpoint fails — `/health` stays healthy so the smoke test passes and the ramp actually starts:
   ```python
   from fastapi import HTTPException
   @app.get("/")
   def read_root():
       raise HTTPException(status_code=500, detail="V3 canary on fire")
   ```
2. Commit and push.
3. The build progresses past smoke (because `/health` is fine). At Stage 1 (10%), the bake step starts sampling the canary URL on `/` and accumulates 5xx responses. Once it exceeds `_MAX_5XX` (default 2), Cloud Build:
   - Calls `gcloud run services update-traffic --to-revisions=<V2>=100 --remove-tags=canary`
   - Exits 1, marking the build as failed
4. Traffic is back to V2 (the previous stable) within seconds. V3 is still deployed as a revision but receives no traffic and has no canary tag.

#### V4 — recovery (optional)
1. Revert the change to `/` so it returns the v1 response again.
2. Push. The pipeline re-runs the full ramp against V2 (still the stable) and V4 graduates cleanly.

---

## 📈 Progressive Canary Promotion

Cloud Build orchestrates the entire ramp inside a single build run.

### Flow

```
deploy --no-traffic --tag=canary
        │
        ▼
smoke test  /health on canary URL  ──► fail ⇒ abort, no traffic shift
        │
        ▼
Stage 1: 10%  ──► bake 2 min, sampling canary URL /
        │              │
        │              └─► 5xx > tolerance ⇒ revert to stable, exit 1
        ▼
Stage 2: 50%  ──► bake 2 min, same check
        │
        ▼
Stage 3: 100%  ──► drop canary tag (revision graduates to stable)
```

### What each stage actually does

| Stage | `gcloud run services update-traffic ...`                                          | Bake action                                  |
|-------|----------------------------------------------------------------------------------|----------------------------------------------|
| 10%   | `--to-revisions=<canary>=10,<stable>=90 --update-tags=canary=<canary>`            | 24 samples × 5s of the canary URL on `/`     |
| 50%   | `--to-revisions=<canary>=50,<stable>=50 --update-tags=canary=<canary>`            | Same                                         |
| 100%  | `--to-revisions=<canary>=100 --remove-tags=canary`                                | (no bake — graduation)                       |

Sampling hits the **canary URL** (the `canary---...run.app` tagged URL), not the service URL — so it directly observes the new revision regardless of traffic percentage. This catches a broken canary fast even when only 10% of users would actually see it.

### What "graduation" means

At Stage 3, Cloud Build:
1. **Sets the canary revision to `100%`** of the traffic split.
2. **Removes the canary tag** — the revision is now the stable. Its tagged URL stops resolving until the next deploy.

The previous stable is no longer in `service.traffic` after graduation. It still exists as a revision (so you can roll back manually via `gcloud run services update-traffic --to-revisions=<old>=100`), and the auto-rollback function will refuse to revert the newly-graduated revision — its safety rule trips on "≥50% traffic + no canary tag".

### Demo timeline

| Time       | Stage           | Traffic split                                |
|------------|-----------------|----------------------------------------------|
| T+0..~2m   | build + scan    | V1: 100% / V2 (canary tag, 0%)               |
| T+~2m      | smoke + Stage 1 | V1: 90% / V2 (canary): 10%                   |
| T+~4m      | Stage 2         | V1: 50% / V2 (canary): 50%                   |
| T+~6m      | Stage 3         | V2: 100% (no tag) — V1 no longer in traffic  |

### Tuning

All knobs are Cloud Build substitutions on `cloudbuild.yaml` — no code change needed:

| Substitution      | Default | Purpose                                                                 |
|-------------------|---------|-------------------------------------------------------------------------|
| `_BAKE_SECONDS`   | `120`   | How long each stage bakes before promoting to the next.                 |
| `_MAX_5XX`        | `2`     | Allowed 5xx responses per bake window before reverting and failing.    |
| `_FAIL_SEVERITIES`| `CRITICAL` | Severities that fail the build at the vulnerability gate. `NONE` disables. |

```bash
# Faster demo (30-second bakes, zero 5xx tolerance):
gcloud builds submit --config demos/deploy-to-cloud-run/cloudbuild.yaml \
  --substitutions=_BAKE_SECONDS=30,_MAX_5XX=0 .
```

Change the stage list itself by editing the bash block in `cloudbuild.yaml` (e.g., add a 25% stage). The structure is a linear sequence of `update-traffic` → `bake` calls — easy to extend.

---

## 🧪 Canary Smoke Test

The pipeline doesn't trust a freshly deployed revision until it answers a real HTTP request. After `gcloud run deploy --tag=canary --no-traffic`, the revision is reachable **only** through its tagged URL — production traffic still goes to V1.

The smoke-test step:
1. Resolves the canary URL by reading `.status.traffic[]` from `gcloud run services describe` and selecting the entry where `tag == "canary"`.
2. Hits `<canary-url>/health` and retries every 5 seconds for up to a minute (12 attempts) to absorb cold-start latency.
3. On the first `200`, prints the response body and continues to the traffic split.
4. After 12 non-200 responses, fails the build — `update-traffic` is never invoked, so no real users see the broken revision.

### Tweaking the smoke test
- **Path:** change `/health` to whatever endpoint you want to validate. For richer checks, replace the single `curl` with a small script that hits multiple paths or validates response bodies with `jq`.
- **Retry budget:** the loop is `seq 1 12` with a 5-second sleep — adjust if your app has a longer cold start.
- **Auth:** the demo service uses `--allow-unauthenticated`. For a private service, swap `curl` for `curl -H "Authorization: Bearer $(gcloud auth print-identity-token)"`.

---

## 🛡️ Vulnerability Scanning Gate

Container Scanning is enabled at the project level via Terraform (`containerscanning.googleapis.com` + `containeranalysis.googleapis.com` in `infra/main.tf`). Once enabled, **every** image pushed to Artifact Registry is scanned automatically — there is no per-repo or per-image flag.

The Cloud Build pipeline turns those findings into a deploy gate:

1. After `docker push`, a `cloud-sdk` step polls `gcloud artifacts docker images describe --show-package-vulnerability` until the scan completes (up to ~5 minutes).
2. It counts findings whose severity matches the `_FAIL_SEVERITIES` substitution (default: `CRITICAL`).
3. If the count is greater than zero, the build exits non-zero and the Cloud Run deploy never runs.

### Tuning the gate
The threshold is a Cloud Build substitution, so you can change it without editing the pipeline:

```bash
# Tighten (block on HIGH as well):
gcloud builds submit --config demos/deploy-to-cloud-run/cloudbuild.yaml \
  --substitutions=_FAIL_SEVERITIES=CRITICAL,HIGH .

# Disable the gate entirely (always deploy, skip the scan check):
gcloud builds submit --config demos/deploy-to-cloud-run/cloudbuild.yaml \
  --substitutions=_FAIL_SEVERITIES=NONE .
```

For the GitHub-triggered build, set the substitution on the trigger itself (Terraform: add a `substitutions` block to `google_cloudbuild_trigger.api_trigger`).

### Required IAM
The build service account needs `roles/containeranalysis.occurrences.viewer` to read scan results. This is wired up in `infra/iam.tf`.

### Inspecting results manually
```bash
gcloud artifacts docker images describe \
  europe-west1-docker.pkg.dev/<PROJECT_ID>/api-repo/my-api:<COMMIT_SHA> \
  --show-package-vulnerability
```

## Cleanup
To avoid incurring future charges, destroy the infrastructure once you are done testing.

Note: You may need to manually delete the Docker images inside your Artifact Registry repository before Terraform can successfully destroy it.

```bash
cd deploy-to-cloud-run/infra/
terraform destroy
```
