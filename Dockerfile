FROM python:3.11-slim

WORKDIR /app

# Install Trivy binary
RUN apt-get update && \
    apt-get install -y wget && \
    wget -qO- https://github.com/aquasecurity/trivy/releases/download/v0.48.0/trivy_0.48.0_Linux-64bit.tar.gz | tar -xz -C /usr/local/bin trivy && \
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
