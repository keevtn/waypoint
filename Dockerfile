# Waypoint: one image, one process. FastAPI serves the API and frontend/dist (SPEC.md §4, §13).
# Build:  docker build -t waypoint .
# Run:    docker run --rm -p 8000:8000 -e DATA_MODE=local -e LLM_FAKE=1 waypoint

# ---- stage 1: build the frontend -------------------------------------------
FROM node:20-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# api.ts globs ../../backend/fixtures/*.json at build time (fixture mode).
COPY backend/fixtures/ /src/backend/fixtures/
RUN npm run build

# ---- stage 2: python runtime -----------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FASTEMBED_CACHE_PATH=/app/.cache/fastembed \
    PORT=8000

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/
COPY scripts/ scripts/
COPY --from=frontend /src/frontend/dist/ frontend/dist/

# Build the RAG index (and download the embedding model into FASTEMBED_CACHE_PATH)
# only once a corpus exists. A failure here fails the build, so Render keeps the
# last good deploy instead of shipping an app without its index.
RUN mkdir -p "$FASTEMBED_CACHE_PATH" \
 && if find backend/corpus -name '*.md' -type f | grep -q .; then \
        cd backend && python ../scripts/build_index.py; \
    else \
        echo "no corpus yet; skipping build_index.py"; \
    fi

# Unprivileged user; backend/ stays writable for the sqlite db.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health', timeout=4)" || exit 1
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
