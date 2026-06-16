FROM aquasec/trivy:latest AS trivy
RUN trivy image --download-db-only

FROM python:3.13-alpine3.23

WORKDIR /app
RUN apk add --no-cache \
    ca-certificates \
    curl \
    docker-cli

COPY --from=trivy /usr/local/bin/trivy /usr/local/bin/trivy
COPY --from=trivy /root/.cache/trivy /root/.cache/trivy
RUN trivy --version

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/
COPY logging_config.json .
COPY asgi.py .

EXPOSE 5000

CMD ["/bin/sh", "-c", "uvicorn asgi:app --host 0.0.0.0 --port 5000 --workers ${UVICORN_WORKERS:-4} --log-config /app/logging_config.json"]
