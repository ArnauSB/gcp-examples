# Serverless CI/CD & Canary Deployments on Google Cloud

This directory contains a complete Infrastructure as Code (IaC) and CI/CD example for deploying a Python FastAPI application to Google Cloud Run using a Canary release strategy (90/10 traffic splitting).

## Architecture Overview

This demo leverages the following Google Cloud Platform services:

* **Cloud Run:** Serverless compute platform to run the API container.
* **Cloud Build:** Serverless CI/CD platform to build the Docker image and execute the deployment steps.
* **Artifact Registry:** Secure private repository to store the built Docker images.
* **Container Scanning / Container Analysis:** Automatically scans every image pushed to Artifact Registry for OS-package CVEs; the pipeline reads the findings and gates the deploy.
* **Cloud IAM:** Least-privilege service accounts to securely execute the pipeline.
* **Terraform:** Provisions the foundational infrastructure and wires the GitHub trigger.

### The Pipeline Flow
1. A push to the `main` branch triggers Google Cloud Build.
2. Cloud Build builds the Docker image and pushes it to Artifact Registry.
3. Artifact Registry scans the image; Cloud Build polls the Container Analysis API and **fails the build** if any finding matches the configured severity threshold (default `CRITICAL`).
4. Cloud Build deploys the new revision to Cloud Run with `0%` initial traffic (`--no-traffic`).
5. Cloud Build executes a traffic update, routing `10%` of the traffic to the new revision and keeping `90%` on the previous stable revision.

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
2. Temporarily comment out the --no-traffic flag in Step 3.
3. Temporarily comment out the entirety of Step 4 (the update-traffic command).
4. Commit and push your code to GitHub. This will deploy the baseline version (V1) taking 100% of the traffic.

### 3. Canary Deployment (V2)
Once V1 is live, you can test the Canary pipeline:

1. Revert `cloudbuild.yaml` to its original state (uncomment --no-traffic and Step 4).
2. Make a visible change to the application code.
3. Commit and push your changes to GitHub.
4. Cloud Build will deploy the new version and automatically split the traffic (90% to V1, 10% to V2).

### 4. Verify Traffic Splitting
You can continuously ping your Cloud Run URL to observe the traffic splitting in action:

```bash
while true; do curl -s https://YOUR_CLOUD_RUN_URL; echo ""; sleep 0.5; done
```

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
