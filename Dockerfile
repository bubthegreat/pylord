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


# ttyd serves the browser terminal (deployed as a sidecar from this same
# image -- see deploy/helm/pylord). Pinned by version and checksum: this is
# a binary from a GitHub release, so an unpinned fetch would let the build
# change under us.
FROM debian:bookworm-slim AS ttyd
ARG TTYD_VERSION=1.7.7
ARG TTYD_SHA256=8a217c968aba172e0dbf3f34447218dc015bc4d5e59bf51db2f2cd12b7be4f55
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && curl -fsSL -o /tmp/ttyd \
      "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.x86_64" \
 && echo "${TTYD_SHA256}  /tmp/ttyd" | sha256sum -c - \
 && chmod +x /tmp/ttyd \
 && rm -rf /var/lib/apt/lists/*


FROM python:3.12-slim-bookworm AS runtime

# The game writes nothing outside /data; run as a non-root user that owns it.
# telnet is the client ttyd drives; nothing in the game container uses it.
RUN apt-get update \
 && apt-get install -y --no-install-recommends telnet \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 pylord \
 && useradd --uid 10001 --gid pylord --create-home --shell /usr/sbin/nologin pylord \
 && mkdir -p /data && chown pylord:pylord /data

WORKDIR /app

COPY --from=ttyd /tmp/ttyd /usr/local/bin/ttyd
COPY --from=builder --chown=pylord:pylord /app/.venv /app/.venv
COPY --chown=pylord:pylord pylord/ ./pylord/
# IGMs are code and ship with the image, next to the package that loads
# them by name. The data volume holds nothing but the database.
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
