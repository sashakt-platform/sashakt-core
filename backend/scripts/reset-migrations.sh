#! /usr/bin/env bash
set -e
set -x

# delete migration files
rm -rf app/alembic/versions/*.py

# reset alembic
alembic stamp base

# generate new migration
alembic revision --autogenerate -m "Initial migration"

# apply migration
alembic upgrade head
