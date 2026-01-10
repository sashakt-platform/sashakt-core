#! /usr/bin/env bash

# exit in case of error
set -e

MIGRATION_MESSAGE=""

# parse arguments
while getopts "m:" opt; do
  case $opt in
    m)
      MIGRATION_MESSAGE=$OPTARG
      ;;
    *)
      echo "Usage: $0 -m <migration_message>"
      exit 1
      ;;
  esac
done

# check if migration message is provided
if [ -z "$MIGRATION_MESSAGE" ]; then
  echo "Error: Migration message (-m) is required."
  echo "Usage: $0 -m <migration_message>"
  exit 1
fi

# run alembic to create migration
docker compose exec backend alembic revision --autogenerate -m "$MIGRATION_MESSAGE"

# sync migration file to file system
./scripts/sync-migrations.sh
