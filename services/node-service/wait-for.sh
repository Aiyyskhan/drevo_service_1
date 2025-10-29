#!/usr/bin/env bash
set -euo pipefail

HOST_RABBIT="rabbitmq"
PORT_RABBIT=5672
HOST_MINIO="minio"
PORT_MINIO=9000

echo "Waiting for $HOST_RABBIT:$PORT_RABBIT..."
for i in {1..30}; do
  if nc -z "$HOST_RABBIT" "$PORT_RABBIT"; then
    echo "$HOST_RABBIT available"
    break
  fi
  echo "  still waiting ($i)..."
  sleep 1
done

echo "Waiting for $HOST_MINIO:$PORT_MINIO..."
for i in {1..30}; do
  if nc -z "$HOST_MINIO" "$PORT_MINIO"; then
    echo "$HOST_MINIO available"
    break
  fi
  echo "  still waiting ($i)..."
  sleep 1
done

echo "Starting node service"
exec node dist/index.js
