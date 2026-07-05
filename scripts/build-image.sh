#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-devops-tools:latest}"

docker build -t "$IMAGE_NAME" .
