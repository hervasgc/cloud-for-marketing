#!/usr/bin/env bash
# Deploys the FoCVS web UI + pipeline to Cloud Run.
#
# What this script does:
#   1. Enables the required GCP APIs.
#   2. Creates a Cloud Storage bucket to durably store run outputs
#      (output/<run-name>/ lives here instead of the container's ephemeral
#      disk, mounted straight into the container as a volume).
#   3. Creates a dedicated, least-privilege service account for the Cloud Run
#      service (read/write access to that one bucket only).
#   4. Builds the container from the Dockerfile in this folder and deploys it
#      to Cloud Run, PRIVATE (--no-allow-unauthenticated) -- nobody can call
#      it until you gate it with Identity-Aware Proxy (see the printed next
#      steps, or the deployment guide artifact).
#
# Usage:
#   PROJECT_ID=my-gcp-project ./deploy_gcp.sh
#
# Optional overrides (env vars):
#   REGION        default: us-central1
#   SERVICE_NAME  default: focvs
#   BUCKET_NAME   default: ${PROJECT_ID}-focvs-runs

set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID, e.g. PROJECT_ID=my-project ./deploy_gcp.sh}"
: "${REGION:=us-central1}"
: "${SERVICE_NAME:=focvs}"
: "${BUCKET_NAME:=${PROJECT_ID}-focvs-runs}"
SA_NAME="focvs-run-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "== Project:  ${PROJECT_ID}"
echo "== Region:   ${REGION}"
echo "== Service:  ${SERVICE_NAME}"
echo "== Bucket:   gs://${BUCKET_NAME}"
echo "== Runtime SA: ${SA_EMAIL}"
echo

gcloud config set project "${PROJECT_ID}" >/dev/null

echo "-- Enabling required APIs (safe to re-run)"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  iap.googleapis.com

echo "-- Ensuring output bucket exists"
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET_NAME}" --location="${REGION}"
else
  echo "   gs://${BUCKET_NAME} already exists, skipping."
fi

echo "-- Ensuring runtime service account exists"
if ! gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="FoCVS Cloud Run runtime"
else
  echo "   ${SA_EMAIL} already exists, skipping."
fi

echo "-- Granting the runtime SA read/write on the bucket only"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin" >/dev/null

echo "-- Building and deploying to Cloud Run (this builds the Dockerfile via Cloud Build)"
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --region "${REGION}" \
  --service-account "${SA_EMAIL}" \
  --execution-environment gen2 \
  --no-allow-unauthenticated \
  --add-volume=name=focvs-data,type=cloud-storage,bucket="${BUCKET_NAME}" \
  --add-volume-mount=volume=focvs-data,mount-path=/mnt/focvs-output \
  --set-env-vars=FOCVS_RUNS_DIR=/mnt/focvs-output,FOCVS_WORK_DIR=/tmp/focvs-work \
  --memory=2Gi \
  --cpu=2 \
  --timeout=3600 \
  --max-instances=3

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format='value(status.url)')

cat <<EOF

== Deploy concluído ==
URL do serviço (ainda privado): ${SERVICE_URL}

Próximos passos (uma vez só, feitos pelo console GCP):
  1. Cloud Run > ${SERVICE_NAME} > aba Segurança/Rede > ativar Identity-Aware Proxy.
     (Isso pode pedir para configurar a tela de consentimento OAuth do projeto,
     se ainda não existir.)
  2. Em IAP, conceder o papel "IAP-secured Web App User" apenas às pessoas
     (e-mails do Workspace) que devem testar o piloto:
       gcloud iap web add-iam-policy-binding \\
         --resource-type=cloud-run \\
         --service=${SERVICE_NAME} \\
         --region=${REGION} \\
         --member="user:pessoa@suaempresa.com" \\
         --role="roles/iap.httpsResourceAccessor"
  3. Reabra ${SERVICE_URL} -- agora exige login Google antes de mostrar a tela
     de upload.

Para atualizar o serviço depois de mudar o código, rode este script de novo.
EOF
