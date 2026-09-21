---
name: reference_github_deployment
description: "GitHub Actions CI/CD setup for automated Cloud Run deployment; includes bucket, IAM, secrets"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 718cda63-9d83-4fdf-adce-f70916e9c981
  modified: 2026-09-21T22:28:42.868Z
---

## GitHub Actions Workflow

**File**: `.github/workflows/deploy-focvs.yml`  
**Trigger**: Push to main branch, filtered by path `marketing-analytics/predicting/future-customer-value-segments/**`

### What it does
1. Checks out code
2. Authenticates to GCP via `secrets.GCP_SA_KEY` (service account JSON)
3. Builds Docker image and deploys to Cloud Run

### Key Config

```yaml
env:
  PROJECT_ID: radiant-tide-401723
  REGION: southamerica-east1
  SERVICE: focvs
  BUCKET: radiant-tide-401723-focvs-runs
```

---

## GCP Setup

### Cloud Run Service
- **Name**: `focvs`
- **Region**: `southamerica-east1` (São Paulo)
- **URL**: https://focvs-zj2e5a77ka-rj.a.run.app (auto-generated)
- **Auth**: `--no-allow-unauthenticated` (private; requires user identity)
- **Execution env**: gen2 (newer, faster)
- **Resources**: 2 CPU, 2Gi memory, 3600s timeout, max 3 instances

### Cloud Storage
- **Bucket**: `radiant-tide-401723-focvs-runs`
- **Purpose**: Persistent output storage (mounted at `/mnt/focvs-output` in Cloud Run)
- **Volume mount**: `gcloud run deploy ... --add-volume=name=focvs-data,type=cloud-storage,bucket=...`

### Service Account
- **Name**: `github-sentimento-analise@radiant-tide-401723.iam.gserviceaccount.com`
- **Role**: Assigned during `gcloud run deploy` (implicitly)
- **Secret in GitHub**: `GCP_SA_KEY` (JSON credentials file)

---

## Environment Variables (Cloud Run)

```
FOCVS_RUNS_DIR=/mnt/focvs-output      (persistent storage)
FOCVS_WORK_DIR=/tmp/focvs-work        (ephemeral; local disk)
```

Webapp (`app.py`) reads these to determine where to save/read run outputs.

---

## Local Equivalent

To simulate Cloud Run environment locally:
```bash
export FOCVS_RUNS_DIR=./output
export FOCVS_WORK_DIR=./.work
python webapp/app.py
```

(Default behavior if env vars not set.)

---

## How to trigger a deploy

1. Make changes locally
2. Commit to git (ensure path matches filter: `marketing-analytics/predicting/future-customer-value-segments/**`)
3. Push to `main`: `git push origin main`
4. GitHub Actions runs automatically → builds → deploys to Cloud Run
5. Check status: https://github.com/hervasgc/cloud-for-marketing/actions

---

## Troubleshooting

### Deploy fails: "Bucket does not exist"
- Ensure bucket `radiant-tide-401723-focvs-runs` exists in GCP
- Verify service account has `roles/storage.objectAdmin` on bucket

### Deploy fails: "Service account not authorized"
- Check `GCP_SA_KEY` secret in GitHub settings (Settings → Secrets → Actions)
- Verify JSON is valid and has correct scopes (Dataflow, Compute, Storage)

### Service won't start: "FOCVS_RUNS_DIR not accessible"
- Verify Cloud Storage bucket is mounted: `gcloud run describe focvs --region southamerica-east1 | grep -A5 volumes`
- Check IAM: service account must have `roles/storage.objectViewer` + `roles/storage.objectCreator`

### Pipeline times out
- Timeout is 3600s per request. Pipelines >1hr may fail.
- Can increase via `gcloud run deploy ... --timeout=7200` but check GCP quotas.

---

## Links

- **Cloud Run service**: https://console.cloud.google.com/run/detail/southamerica-east1/focvs
- **Cloud Storage bucket**: https://console.cloud.google.com/storage/browser/radiant-tide-401723-focvs-runs
- **GitHub Actions runs**: https://github.com/hervasgc/cloud-for-marketing/actions
- **GCP Project**: https://console.cloud.google.com/welcome?project=radiant-tide-401723
