#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

# Print usage helper
usage() {
  echo "Usage: $0 <REGION> <PROJECT_ID> <REPOSITORY_NAME> [IMAGE_TAG] [--local]"
  echo "Example: $0 us-central1 my-observability-project my-docker-repo v1"
  echo "By default, Google Cloud Build is used. Pass --local to build via local Docker instead."
  exit 1
}

# Parse positional arguments and optional flags safely
POSITIONAL_ARGS=()
USE_LOCAL=false
for arg in "$@"; do
  if [ "$arg" = "--local" ]; then
    USE_LOCAL=true
  else
    POSITIONAL_ARGS+=("$arg")
  fi
done

# Validate inputs
if [ ${#POSITIONAL_ARGS[@]} -lt 3 ]; then
  usage
fi

REGION="${POSITIONAL_ARGS[0]}"
PROJECT_ID="${POSITIONAL_ARGS[1]}"
REPO_NAME="${POSITIONAL_ARGS[2]}"
IMAGE_TAG="${POSITIONAL_ARGS[3]:-latest}"

IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/ces-tracer:${IMAGE_TAG}"

# Get folder script context
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${SCRIPT_DIR}/src"

echo "=========================================================="
echo "Preparing to Build CES Tracer Container Image"
echo "Target Image Path: ${IMAGE_PATH}"
echo "Source Directory: ${SRC_DIR}"
echo "=========================================================="
echo ""

if [ "$USE_LOCAL" = true ]; then
  echo "Running local Docker build (--local flag active)..."
  docker build -t "${IMAGE_PATH}" "${SRC_DIR}"
  echo "Pushing local Docker image to Artifact Registry..."
  docker push "${IMAGE_PATH}"
else
  echo "Running Google Cloud Build (Default)..."
  gcloud builds submit "${SRC_DIR}" \
    --tag "${IMAGE_PATH}" \
    --project "${PROJECT_ID}"
fi

echo ""
echo "=========================================================="
echo "Successfully completed build and push process!"
echo "You can now pass this image path to your Terraform variables:"
echo "image_url = \"${IMAGE_PATH}\""
echo "=========================================================="
