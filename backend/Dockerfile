FROM python:3.10

ENV PYTHONUNBUFFERED=1

WORKDIR /app/

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV PATH="/app/.venv/bin:$PATH"

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

# Install dependencies
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync --frozen --no-install-project

ENV PYTHONPATH=/app

COPY ./scripts /app/scripts

COPY ./pyproject.toml ./uv.lock ./alembic.ini /app/

COPY ./app /app/app

# Install tzdata for timezone support at runtime and also libmagic for file type detection
RUN apt-get update && \
  apt-get install -y --no-install-recommends tzdata && \
  apt-get install -y libmagic1 && \
  rm -rf /var/lib/apt/lists/*

# Create timezone setup script that runs at container startup
RUN echo '#!/bin/bash\nif [ ! -z "$TIMEZONE" ]; then\n  ln -snf /usr/share/zoneinfo/$TIMEZONE /etc/localtime\n  echo $TIMEZONE > /etc/timezone\nfi\nexec "$@"' > /app/setup-timezone.sh && \
  chmod +x /app/setup-timezone.sh

# Sync the project
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync

ENTRYPOINT ["/app/setup-timezone.sh"]
CMD ["fastapi", "run", "--workers", "4", "app/main.py"]
