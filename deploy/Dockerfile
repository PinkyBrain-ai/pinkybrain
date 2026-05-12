# PinkyBrain Dockerfile — Production-ready, non-root, hardened
# Build: docker build -t pinkybrain/server:latest .
# Run:  docker compose up -d

FROM python:3.11-slim AS base

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user early
RUN groupadd -r pinkybrain && \
    useradd -r -m -d /data -g pinkybrain -s /sbin/nologin pinkybrain

# Install PinkyBrain
COPY . /opt/pinkybrain/
RUN pip install --no-cache-dir --prefer-binary /opt/pinkybrain

# Data volume
VOLUME /data

# Ports: 8080 (private API), 8090 (public mesh)
EXPOSE 8080 8090

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8080/api/ping || exit 1

# Run as non-root user
USER pinkybrain

# Default config path
ENV PINKYBRAIN_CONFIG=/data/config.json
ENV PINKYBRAIN_DATA_DIR=/data
ENV OLLAMA_HOST=host.docker.internal:11434

WORKDIR /data

ENTRYPOINT ["tini", "--"]
CMD ["pinkybrain", "serve", "--config", "/data/config.json"]