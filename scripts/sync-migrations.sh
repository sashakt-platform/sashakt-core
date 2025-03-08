#!/bin/bash

CONTAINER_NAME=sashakt-core-backend-1
CONTAINER_PATH=app/app/alembic/versions
HOST_PATH=./backend/app/alembic

echo "Syncing migrations from container to host..."
docker cp $CONTAINER_NAME:$CONTAINER_PATH $HOST_PATH
