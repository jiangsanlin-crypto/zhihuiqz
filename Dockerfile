FROM python:3.12-slim

# Optional build mirrors for regions where upstream Debian/PyPI is slow or
# partially unreachable (e.g. mainland China CI/CD hosts). Both default to
# empty, so upstream behaviour is unchanged when they are not provided.
ARG APT_MIRROR=""
ARG PIP_INDEX_URL=""

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN if [ -n "$APT_MIRROR" ]; then \
      sed -i "s|deb.debian.org|$APT_MIRROR|g; s|security.debian.org|$APT_MIRROR|g" \
        /etc/apt/sources.list /etc/apt/sources.list.d/*.sources 2>/dev/null || true; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN if [ -n "$PIP_INDEX_URL" ]; then \
      pip config set global.index-url "$PIP_INDEX_URL"; \
      pip config set global.trusted-host "$(printf '%s' "$PIP_INDEX_URL" | sed -E 's#^https?://([^/]+).*#\1#')"; \
    fi \
    && pip install --no-cache-dir -r requirements.txt

COPY orchestrator ./orchestrator
COPY agents ./agents
COPY tasks ./tasks
COPY docs ./docs
COPY scripts ./scripts
COPY tests ./tests

RUN mkdir -p /app/data

EXPOSE 8080
CMD ["uvicorn","orchestrator.control_service:create_app","--factory","--host","0.0.0.0","--port","8080"]
