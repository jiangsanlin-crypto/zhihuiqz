FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY orchestrator ./orchestrator
COPY agents ./agents
COPY tasks ./tasks
COPY docs ./docs
COPY tests ./tests

RUN mkdir -p /app/data

EXPOSE 8080
CMD ["uvicorn","orchestrator.main:app","--host","0.0.0.0","--port","8080"]
