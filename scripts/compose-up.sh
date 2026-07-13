#!/usr/bin/env bash
set -euo pipefail

mkdir -p data media
docker compose up -d --build
docker compose ps
