#!/usr/bin/env bash

set -e
set -x

coverage run --source=app -m pytest
coverage report --show-missing
pytest --cov=app --cov-branch --cov-report=xml
