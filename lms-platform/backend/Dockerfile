# Build from lms-platform, so the image also contains Alembic migrations.
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend
COPY backend/requirements.runtime.lock.txt ./requirements.runtime.lock.txt
RUN --mount=type=secret,id=pip_ca \
    if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; \
    pip install --no-cache-dir -r requirements.runtime.lock.txt \
    && groupadd --gid 10001 lms \
    && useradd --uid 10001 --gid lms --no-create-home lms

COPY backend/src ./src
COPY backend/alembic.ini ./alembic.ini
COPY database/migrations /app/database/migrations

USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "src.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
