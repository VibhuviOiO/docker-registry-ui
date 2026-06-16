###############################
#        BUILDER STAGE        #
###############################
FROM python:3.13-alpine3.23 AS builder

WORKDIR /app

# Install tools required only during build
RUN apk add --no-cache curl tar ca-certificates

# Detect system architecture and download the latest stable Trivy release
RUN ARCH="$(apk --print-arch)"; \
    case "$ARCH" in \
        x86_64)   TRIVY_ARCH="64bit" ;; \
        aarch64)  TRIVY_ARCH="ARM64" ;; \
        armv7)    TRIVY_ARCH="ARM" ;; \
        ppc64le)  TRIVY_ARCH="PPC64LE" ;; \
        s390x)    TRIVY_ARCH="s390x" ;; \
        *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac && \
    TRIVY_VERSION="$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/aquasecurity/trivy/releases/latest | sed 's#.*/tag/##')" && \
    [ -n "$TRIVY_VERSION" ] || (echo "Failed to resolve Trivy version" && exit 1) && \
    echo "Downloading Trivy $TRIVY_VERSION for $TRIVY_ARCH" && \
    curl -fsSL -o /tmp/trivy.tar.gz \
        "https://github.com/aquasecurity/trivy/releases/download/${TRIVY_VERSION}/trivy_${TRIVY_VERSION#v}_Linux-${TRIVY_ARCH}.tar.gz" && \
    tar -xzf /tmp/trivy.tar.gz -C /usr/local/bin trivy && \
    rm -f /tmp/trivy.tar.gz && \
    chmod +x /usr/local/bin/trivy

# Install Python dependencies into a separate directory
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


###############################
#        RUNTIME STAGE        #
###############################
FROM python:3.13-alpine3.23 AS runtime

WORKDIR /app

# Copy Trivy binary from builder stage
COPY --from=builder /usr/local/bin/trivy /usr/local/bin/trivy

# Copy installed Python packages
COPY --from=builder /install /usr/local

# Copy application source code
COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/
COPY asgi.py .

EXPOSE 5000

CMD ["uvicorn", "asgi:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "4", "--log-level", "info", "--access-log"]
