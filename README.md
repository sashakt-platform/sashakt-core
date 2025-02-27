# Sashakt Platform

## Pre-requisites

- [uv](https://docs.astral.sh/uv/) for Python package and environment management.

## Setup project

- Clone the repo
- Set `UV_PREVIEW=1` in your environment variable so that you don't need to pass extra argument

```bash
uv sync
```

or

```bash
uv sync --preview
```

## Run project

Dev server

```bash
uv run fastapi dev src/app/main.py
```

## Tests

```bash
uv run pytest
```

## Code formatting

We are using ruff for formatting and linting, please ensure your editor is configured for the same.

We have also added pre-commit hook to check the same and also CI job for the same.

In order to setup pre-commit hook locally run following command:

```bash
uv run pre-commit install
```
