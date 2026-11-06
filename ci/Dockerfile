# syntax=docker/dockerfile:1
ARG NODE_IMAGE=node:24-bookworm-slim
ARG PYTHON_IMAGE=python:3.14-slim-bookworm
FROM ${NODE_IMAGE} AS node
FROM ${PYTHON_IMAGE}

ARG CI_IMAGE_KEY
ARG BENCH_VERSION
LABEL org.opencontainers.image.source="https://github.com/frankymcgee/verto" \
      org.opencontainers.image.description="Reusable Verto v16 CI bench with a synthetic database seed" \
      io.webwire.verto-ci.key="${CI_IMAGE_KEY}"

ENV CI=Yes FRAPPE_DOCKER_BUILD=1 PYTHONUNBUFFERED=1 \
    VERTO_CI_BENCH=/opt/frappe-bench
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
      git curl ca-certificates rsync build-essential pkg-config \
      libmariadb-dev libpq-dev libffi-dev libssl-dev libjpeg62-turbo-dev zlib1g-dev \
      libmagic1 libpango-1.0-0 libpangoft2-1.0-0 fonts-dejavu-core \
      mariadb-server mariadb-client redis-server \
    && rm -rf /var/lib/apt/lists/* /var/lib/mysql/* \
    && npm install --global yarn@1.22.22 \
    && pip install --no-cache-dir "frappe-bench==${BENCH_VERSION}" \
    && useradd --create-home --uid 1001 --shell /bin/bash frappe \
    && mkdir -p /opt/verto-ci /opt/frappe-bench \
    && chown -R frappe:frappe /opt/verto-ci /opt/frappe-bench

COPY --chown=frappe:frappe ci/ /opt/verto-ci/
COPY --chown=frappe:frappe . /opt/verto-source/
USER frappe
WORKDIR /opt
RUN python /opt/verto-ci/prepare_bench.py \
    && printf '%s\n' "${CI_IMAGE_KEY}" > /opt/verto-ci/image-key \
    && bash /opt/verto-ci/seed.sh \
    && rm -rf /opt/verto-source /home/frappe/.cache/pip
WORKDIR /opt/frappe-bench
CMD ["bash", "/opt/verto-ci/run.sh", "integration"]
