#! /usr/bin/env bash

# Exit in case of error
set -e

# delete existing migrtaions

rm -rf backend/app/alembic/versions/*.py

docker compose exec backend bash scripts/reset-migrations.sh

./scripts/sync-migrations.sh
