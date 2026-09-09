# Build from lms-platform, so the image also contains Alembic migrations.
ARG RUNTIME_BASE=python:3.11-slim-bookworm
FROM scratch AS wheelhouse
COPY backend/.wheels /wheels

FROM ${RUNTIME_BASE}
USER root

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend
COPY backend/requirements.runtime.lock.txt ./requirements.runtime.lock.txt
RUN --mount=type=secret,id=pip_ca \
    --mount=type=bind,from=wheelhouse,source=/wheels,target=/wheels \
    if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; \
    if [ -n "$(find /wheels -name '*.whl' -print -quit)" ]; then \
        pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.runtime.lock.txt; \
    else \
        pip install --no-cache-dir --timeout 120 --retries 5 -r requirements.runtime.lock.txt; \
    fi \
    && pip check \
    && (getent group lms || groupadd --gid 10001 lms) \
    && (id lms || useradd --uid 10001 --gid lms --no-create-home lms) \
    && rm -rf /app/backend/src /app/database/migrations

COPY backend/src ./src
COPY backend/alembic.ini ./alembic.ini
COPY database/migrations /app/database/migrations

USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "src.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
