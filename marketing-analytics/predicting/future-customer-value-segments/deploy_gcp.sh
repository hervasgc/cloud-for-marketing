#!/usr/bin/env bash
# Manual/one-off deploy of the FoCVS web UI + pipeline to Cloud Run.
#
# The canonical deploy path is .github/workflows/deploy-focvs.yml (runs on
# every push to main that touches this folder). Use this script only for a
# one-off deploy from your own machine -- e.g. to test a change before
# pushing, or to bootstrap the Cloud Storage bucket the first time.
#
# Reuses the same service account as the rest of the org's GCP prototypes in
# this project (github-sentimento-analise) -- see PROJECT_CONTEXT.md in the
# AI-Youtube-Shorts-Generator repo for why. No new service account or IAM
# binding is created by this script.
#
# Usage (defaults match the confirmed plan; override any of these env vars):
#   ./deploy_gcp.sh
#
#   PROJECT_ID    default: radiant-tide-401723
#   REGION        default: southamerica-east1
#   SERVICE_NAME  default: focvs
#   BUCKET_NAME   default: ${PROJECT_ID}-focvs-runs
#   RUNTIME_SA    default: github-sentimento-analise@${PROJECT_ID}.iam.gserviceaccount.com

set -euo pipefail

: "${PROJECT_ID:=radiant-tide-401723}"
: "${REGION:=southamerica-east1}"
: "${SERVICE_NAME:=focvs}"
: "${BUCKET_NAME:=${PROJECT_ID}-focvs-runs}"
: "${RUNTIME_SA:=github-sentimento-analise@${PROJECT_ID}.iam.gserviceaccount.com}"

echo "== Project:    ${PROJECT_ID}"
echo "== Region:     ${REGION}"
echo "== Service:    ${SERVICE_NAME}"
echo "== Bucket:     gs://${BUCKET_NAME}"
echo "== Runtime SA: ${RUNTIME_SA}"
echo

gcloud config set project "${PROJECT_ID}" >/dev/null

echo "-- Ensuring output bucket exists"
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET_NAME}" \
    --location="${REGION}" \
    --uniform-bucket-level-access \
    --public-access-prevention
else
  echo "   gs://${BUCKET_NAME} already exists, skipping."
fi

echo "-- Building and deploying to Cloud Run (this builds the Dockerfile via Cloud Build)"
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --service-account "${RUNTIME_SA}" \
  --execution-environment gen2 \
  --no-allow-unauthenticated \
  --add-volume=name=focvs-data,type=cloud-storage,bucket="${BUCKET_NAME}" \
  --add-volume-mount=volume=focvs-data,mount-path=/mnt/focvs-output \
  --set-env-vars=FOCVS_RUNS_DIR=/mnt/focvs-output,FOCVS_WORK_DIR=/tmp/focvs-work \
  --memory=2Gi \
  --cpu=2 \
  --timeout=3600 \
  --max-instances=3

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.url)')

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

Deploys seguintes: só dê push na main (.github/workflows/deploy-focvs.yml
cuida do resto). Rode este script de novo apenas para um deploy manual pontual.
EOF
