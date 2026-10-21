FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --create-home --uid 10001 app
COPY --chown=app:app app ./app
COPY --chown=app:app web ./web
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && mkdir -p /app/dados && chown app:app /app/dados

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/saude', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header", "--no-access-log"]
