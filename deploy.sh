#!/usr/bin/env bash
# Deploy to server
# Usage: ./deploy.sh

set -euo pipefail

SERVER="root@91.218.247.179"

echo -e "\033[36m=== Cleanup cache ===\033[0m"
find bot webapp -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
echo -e "\033[32m[OK] Cache cleaned\033[0m"

echo -e "\033[36m=== Upload files ===\033[0m"
scp -r bot/ webapp/ nginx/ Dockerfile docker-compose.yml requirements.txt "${SERVER}:/root/schedule/"
echo -e "\033[32m[OK] Files uploaded\033[0m"

echo -e "\033[36m=== Rebuild bot ===\033[0m"
ssh "$SERVER" "cd /root/schedule && docker compose up --build -d bot"

echo -e "\033[36m=== Restart nginx ===\033[0m"
ssh "$SERVER" "cd /root/schedule && docker compose restart nginx"

echo -e "\033[32m=== Done ===\033[0m"
ssh "$SERVER" "cd /root/schedule && docker compose ps"