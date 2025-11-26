#!/usr/bin/env bash
set -e
cd infra
docker compose up --build -d
echo "API en http://localhost:8000/health"
