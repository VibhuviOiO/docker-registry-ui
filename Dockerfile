FROM python:3.11-slim

WORKDIR /app

ARG TRIVY_VERSION=0.71.1
ARG TARGETARCH

# Install Trivy binary (supports amd64 and arm64)
RUN apt-get update && \
    apt-get install -y --no-install-recommends wget ca-certificates && \
    wget -qO- https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-${TARGETARCH}.tar.gz | tar -xz -C /usr/local/bin trivy && \
    chmod +x /usr/local/bin/trivy && \
    apt-get remove -y wget && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/
COPY asgi.py .

EXPOSE 5000

CMD ["uvicorn", "asgi:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "4", "--log-level", "info", "--access-log"]
