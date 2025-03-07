# Sashakt Platform

[![codecov](https://codecov.io/gh/sashakt-platform/sashakt-backend/graph/badge.svg?token=4GXQFZHIJT)](https://codecov.io/gh/sashakt-platform/sashakt-backend) [![Run tests](https://github.com/sashakt-platform/sashakt-backend/actions/workflows/tests.yml/badge.svg)](https://github.com/sashakt-platform/sashakt-backend/actions/workflows/tests.yml)

## Pre-requisites

- [docker](https://docs.docker.com/get-started/get-docker/)
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

## Backend Development

Backend docs: [backend/README.md](./backend/README.md).

## Deployment

Deployment docs: [deployment.md](./deployment.md).

## Development

General development docs: [development.md](./development.md).

This includes using Docker Compose, custom local domains, `.env` configurations, etc.

## Credits

This project was created using [full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template). A big thank you to the team for creating and maintaining the template!!!
