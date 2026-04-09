#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "${EUID}" -ne 0 ]]; then
  SUDO="sudo"
else
  SUDO=""
fi

if ! command -v apt-get >/dev/null 2>&1; then
  exit 1
fi

$SUDO apt-get update -y
$SUDO apt-get install -y docker.io || true
$SUDO apt-get install -y docker-compose-plugin || true
$SUDO apt-get install -y docker-compose || true
$SUDO systemctl enable docker
$SUDO systemctl start docker

if ! id -nG "$USER" | grep -qw docker; then
  $SUDO usermod -aG docker "$USER" || true
fi

if docker compose version >/dev/null 2>&1; then
  docker compose pull
  docker compose up -d
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose pull
  docker-compose up -d
else
  exit 1
fi
