# Serverless CI/CD & Canary Deployments on Google Cloud

This directory contains a complete Infrastructure as Code (IaC) and CI/CD example for deploying a Python FastAPI application to Google Cloud Run using a Canary release strategy (90/10 traffic splitting).

## Architecture Overview

This demo leverages the following Google Cloud Platform services:

* **Cloud Run:** Serverless compute platform to run the API container.
* **Cloud Build:** Serverless CI/CD platform to build the Docker image and execute the deployment steps.
* **Artifact Registry:** Secure private repository to store the built Docker images.
* **Container Scanning / Container Analysis:** Automatically scans every image pushed to Artifact Registry for OS-package CVEs; the pipeline reads the findings and gates the deploy.
* **Cloud Monitoring + Pub/Sub + Cloud Functions:** Detect 5xx-rate breaches on the canary revision and automatically roll traffic back to the previous stable revision.
* **Cloud IAM:** Least-privilege service accounts to securely execute the pipeline.
* **Terraform:** Provisions the foundational infrastructure and wires the GitHub trigger.

### The Pipeline Flow
1. A push to the `main` branch triggers Google Cloud Build.
2. Cloud Build builds the Docker image and pushes it to Artifact Registry.
3. Artifact Registry scans the image; Cloud Build polls the Container Analysis API and **fails the build** if any finding matches the configured severity threshold (default `CRITICAL`).
4. Cloud Build deploys the new revision to Cloud Run with `0%` initial traffic (`--no-traffic`) and attaches the `canary` tag, giving the revision a stable URL like `https://canary---my-api-service-<hash>.<region>.run.app`.
5. Cloud Build smoke-tests the canary revision by calling its tagged URL's `/health` endpoint. If the smoke test fails, the build fails and **no traffic is shifted**.
6. Cloud Build executes a traffic update, routing `10%` of the traffic to the new revision and keeping `90%` on the previous stable revision.
7. After traffic is split, **Cloud Monitoring** watches the canary's 5xx rate. If it breaches the SLO, a **Pub/Sub-triggered Cloud Function** automatically rolls traffic back to the previous stable revision — no human intervention required.

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

### 2. Initial Deployment (V1)
By default, the `cloudbuild.yaml` is configured for a canary deployment. However, a canary deployment requires an existing baseline revision serving 100% of the traffic.

For your very first deployment:

1. Open `cloudbuild.yaml`.
2. Temporarily comment out the `--no-traffic` flag in the **Deploy to Cloud Run** step.
3. Temporarily comment out the entirety of the **Update Traffic Splitting** step.
4. Commit and push your code to GitHub. This will deploy the baseline version (V1) taking 100% of the traffic.

> The vulnerability gate and the smoke test both still run for V1. The smoke test resolves the `canary`-tagged URL (which on V1 just points to the only revision) and confirms `/health` returns 200 before the build is marked successful.

### 3. Canary Deployment (V2)
Once V1 is live, you can test the Canary pipeline:

1. Revert `cloudbuild.yaml` to its original state (uncomment `--no-traffic` and the **Update Traffic Splitting** step).
2. Make a visible change to the application code.
3. Commit and push your changes to GitHub.
4. Cloud Build deploys V2 with `--no-traffic --tag=canary`, smoke-tests it against its tagged URL, and only then splits the traffic (90% to V1, 10% to V2).
5. If the smoke test fails (e.g. you ship a broken `/health`), the build aborts before `update-traffic` runs — V1 keeps 100% of the traffic.

### 4. Verify Traffic Splitting
You can continuously ping your Cloud Run URL to observe the traffic splitting in action:

```bash
while true; do curl -s https://YOUR_CLOUD_RUN_URL; echo ""; sleep 0.5; done
```

---

## ⏪ Automated Rollback on SLO Breach

Smoke tests catch *broken* canaries; they don't catch canaries that pass `/health` but then fall over under real traffic. For that, the demo wires up an automatic rollback path.

### How it works

```
Cloud Run 5xx metric  ─►  Cloud Monitoring alert policy
                                 │
                                 ▼
                  Pub/Sub topic (canary-rollback-alerts)
                                 │
                                 ▼
                  Cloud Function (canary-rollback)
                                 │
                                 ▼
           gcloud run services update-traffic  ──►  100% to previous stable
```

1. A **Cloud Monitoring alert policy** ([rollback.tf](deploy-to-cloud-run/infra/rollback.tf)) watches `run.googleapis.com/request_count` filtered by `response_code_class = 5xx`, grouped by `revision_name`. Threshold: `> 2` 5xx req/min over a 60-second window — loose by design, so it's easy to demo. Tighten by editing `threshold_value` and `duration`.
2. The alert routes through a **Pub/Sub notification channel**, publishing the incident payload to the `canary-rollback-alerts` topic.
3. A **Cloud Function (Python 3.11, 2nd gen)** subscribes to the topic via Eventarc. Source lives in [rollback-function/](deploy-to-cloud-run/rollback-function/).
4. The function uses the **Cloud Run Admin API** (`google-cloud-run`) to:
   - Look up the offending revision in `service.traffic`
   - **Refuse** to roll back if that revision carries ≥50% of traffic and has no canary tag (safety against reverting the stable in a real outage)
   - Otherwise, rewrite the traffic split so the largest *other* revision gets 100%

### Triggering it deliberately
The cleanest way to demo it is to ship a canary that returns 500 on the root path:

```python
@app.get("/")
def read_root():
    raise HTTPException(status_code=500, detail="canary on fire")
```

Push, let the canary smoke test pass on `/health`, let traffic split 90/10, then loop `curl` against the service URL. Once a handful of requests hit the broken 10%, the alert fires and the function reverts traffic to V1.

### Watching it work
- **Alert state:** Cloud Monitoring → Alerting → `Cloud Run canary 5xx rate`
- **Function logs:** Cloud Functions → `canary-rollback` → Logs. You'll see either `Rolling back: <bad> -> <stable>` or the `refusing to auto-roll-back the stable revision` safety message.
- **Final traffic split:** `gcloud run services describe my-api-service --region=europe-west1 --format='value(status.traffic)'`

### Tuning
- **Threshold:** change `threshold_value` / `duration` on `google_monitoring_alert_policy.canary_5xx`. Real services would use an SLO-burn-rate alert instead of raw 5xx count.
- **Safety policy:** the `>= 50% AND no canary tag` heuristic lives in [rollback-function/main.py](deploy-to-cloud-run/rollback-function/main.py). Adjust to taste — e.g., require the canary tag explicitly before rolling back.
- **Retry policy:** the function trigger uses `RETRY_POLICY_DO_NOT_RETRY` so a transient API error doesn't double-roll-back. Switch to `RETRY_POLICY_RETRY` if you'd rather pay the risk.

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
