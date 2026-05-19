#!/bin/bash
set -e

# Extract Project ID from gcloud
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
  echo "Error: No active project found. Configure via 'gcloud config set project <PROJECT_ID>'."
  exit 1
fi

echo "Deploying DietCode Firebase Frontend and Security Rules for Project: $PROJECT_ID"

# 1. Select the project context
firebase use "$PROJECT_ID" || firebase use --add "$PROJECT_ID"

# 2. Build the React Frontend App
echo "Compiling React Frontend Production Bundle..."
cd web
npm run build
cd ..

# 3. Deploy to Firebase
echo "Deploying to Firebase Hosting & Firestore Security Rules..."
firebase deploy --only hosting,firestore

echo "DietCode Control Plane deployed successfully!"
