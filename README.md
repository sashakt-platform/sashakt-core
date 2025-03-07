# Sashakt Platform

[![codecov](https://codecov.io/gh/sashakt-platform/sashakt-core/graph/badge.svg?token=4GXQFZHIJT)](https://codecov.io/gh/sashakt-platform/sashakt-core) [![Run tests](https://github.com/sashakt-platform/sashakt-core/actions/workflows/test-backend.yml/badge.svg)](https://github.com/sashakt-platform/sashakt-core/actions/workflows/test-backend.yml)

## Pre-requisites

- [docker](https://docs.docker.com/get-started/get-docker/) Docker
- [uv](https://docs.astral.sh/uv/) for Python package and environment management.

## Project Setup

You can **just fork or clone** this repository and use it as is.

✨ It just works. ✨

### Configure

Create env file using example file

```bash
cp .env.example .env
```

You can then update configs in the `.env` files to customize your configurations.

Before deploying it, make sure you change at least the values for:

- `SECRET_KEY`
- `FIRST_SUPERUSER_PASSWORD`
- `POSTGRES_PASSWORD`

You can (and should) pass these as environment variables from secrets.

Read the [deployment.md](./deployment.md) docs for more details.

### Generate Secret Keys

Some environment variables in the `.env` file have a default value of `changethis`.

You have to change them with a secret key, to generate secret keys you can run the following command:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the content and use that as password / secret key. And run that again to generate another secure key.

## Boostrap

This is a dockerized setup, hence start the project using below command

```bash
docker compose up -d
```

This should start all necessary services for the project.

You verify backend running by doing health-check

```bash
curl http://[your-domain]:8000/api/v1/utils/health-check/
```

or by visiting: http://[your-domain]:8000/api/v1/utils/health-check/ in the browser

## Backend Development

Backend docs: [backend/README.md](./backend/README.md).

## Development

General development docs: [development.md](./development.md).

This includes using Docker Compose, custom local domains, `.env` configurations, etc.

## Deployment

Deployment docs: [deployment.md](./deployment.md).

## Credits

This project was created using [full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template). A big thank you to the team for creating and maintaining the template!!!
