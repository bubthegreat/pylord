# pylord -- Legend of the Red Dragon telnet server.
#
# Two stages: the first resolves the locked dependency set into a virtualenv,
# the second carries only that venv and the source. Nothing in reference/ or
# tests/ ships (see .dockerignore) -- reference/lord.js is a licence-provenance
# artifact for the repo, not a runtime input.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so a source-only change reuses this layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY pylord/ ./pylord/
RUN uv sync --frozen --no-dev


FROM python:3.12-slim-bookworm AS runtime

# The game writes nothing outside /data; run as a non-root user that owns it.
RUN groupadd --gid 10001 pylord \
 && useradd --uid 10001 --gid pylord --create-home --shell /usr/sbin/nologin pylord \
 && mkdir -p /data && chown pylord:pylord /data

WORKDIR /app

COPY --from=builder --chown=pylord:pylord /app/.venv /app/.venv
COPY --chown=pylord:pylord pylord/ ./pylord/
# The bundled IGMs are seeded into the data volume at startup (the loader
# resolves igms/ next to the database) -- see the chart's init container.
COPY --chown=pylord:pylord igms/ ./igms/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER pylord
EXPOSE 2323
VOLUME ["/data"]

# ENTRYPOINT is the binary, CMD the default arguments: a deployment that
# overrides `args` (the Helm chart does, to point at its own config path)
# replaces only the arguments. With the command baked into CMD alone, any
# `args` override would replace the whole line and the container would try
# to exec "serve" as a binary.
#
# config.toml is supplied by the deployment (a ConfigMap in Kubernetes, a
# bind mount locally); /config/config.toml is where the chart mounts it.
ENTRYPOINT ["pylord"]
CMD ["serve", "--config", "/config/config.toml"]
