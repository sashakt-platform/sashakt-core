#! /usr/bin/env bash

# Exit in case of error
set -e

# run migrtaions
docker compose exec backend alembic upgrade head
