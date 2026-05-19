#!/bin/bash
set -e

# Set default GCP configuration
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
  echo "Error: No active GCP project configured. Please run 'gcloud config set project <PROJECT_ID>'."
  exit 1
fi

echo "Deploying DietCode GCP Infrastructure for Project: $PROJECT_ID"

# 1. Enable Required Services
echo "Enabling GCP API Services..."
gcloud services enable \
  run.googleapis.com \
  cloudtasks.googleapis.com \
  cloudbuild.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com

# 2. Create GCS Artifact Storage Bucket
BUCKET_NAME="operator-artifacts-$PROJECT_ID"
if gsutil ls -b "gs://$BUCKET_NAME" >/dev/null 2>&1; then
  echo "Cloud Storage Bucket gs://$BUCKET_NAME already exists."
else
  echo "Creating Cloud Storage Bucket: gs://$BUCKET_NAME"
  gsutil mb -l us-central1 "gs://$BUCKET_NAME" || true
fi

# 3. Create Cloud Tasks Queue
QUEUE_NAME="operator-queue"
if gcloud tasks queues describe "$QUEUE_NAME" --location=us-central1 >/dev/null 2>&1; then
  echo "Cloud Tasks Queue '$QUEUE_NAME' already exists."
else
  echo "Creating Cloud Tasks Queue: $QUEUE_NAME"
  gcloud tasks queues create "$QUEUE_NAME" --location=us-central1 || true
fi

# 4. Build and Deploy Operator API via Cloud Build
echo "Building and Deploying Control Plane Operator API to Cloud Run..."
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=COMMIT_SHA="latest"

echo "DietCode Control Plane Operator API deployed successfully!"
