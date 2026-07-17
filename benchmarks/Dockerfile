# syntax=docker/dockerfile:1.7
FROM python:3.12.8-slim@sha256:8859bd6ca943079262c27e38b7119cdacede77c463139a15651dd340087a6cc9 AS runtime
ARG VCS_REF=unknown
LABEL org.opencontainers.image.source="https://github.com/corpobear/MCIFT-Benchmarks" \
      org.opencontainers.image.revision=$VCS_REF \
      org.opencontainers.image.licenses="AGPL-3.0-only"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/app/src
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
WORKDIR /app
COPY requirements.lock ./
RUN python -m pip install --require-hashes -r requirements.lock
COPY pyproject.toml ./
COPY src ./src
COPY configs ./configs
COPY schemas ./schemas
USER 10001:10001
ENTRYPOINT ["python", "-m", "mcift_benchmarks"]
