#! /usr/bin/env bash

# Populate a freshly-reset database with sample data for manual testing.
# Safe to re-run — the script detects existing sample data and exits early.
#
# Prerequisite: the backend container is running and `initial_data.py` has
# already created roles, permissions, location data, and the superuser.

set -e

docker compose exec backend python app/populate_sample_data.py
