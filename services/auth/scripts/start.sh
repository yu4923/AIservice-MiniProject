#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  echo "services/auth/.env is required" >&2
  exit 1
fi
# 어느 한 컨테이너가 종료되면 나머지도 종료해 같은 실행 수명으로 관리한다.
exec docker compose --env-file .env up --build --abort-on-container-exit
