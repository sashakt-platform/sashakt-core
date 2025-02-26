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
