FROM python:3.12-slim

# git and grep are used by the workspace tools.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies are installed BEFORE the source is copied so that this layer is
# shared across all five agents. Only the first agent pays the install cost.
RUN pip install --no-cache-dir \
    "openai-agents>=0.0.7" \
    "httpx>=0.27.0" \
    "a2a-sdk[http-server]==1.1.0" \
    "python-dotenv>=1.0.0" \
    "uvicorn>=0.30.0" \
    "click>=8.0.0" \
    "opentelemetry-sdk>=1.25.0" \
    "opentelemetry-distro>=0.46b0" \
    "opentelemetry-exporter-otlp>=1.25.0" \
    "opentelemetry-exporter-otlp-proto-grpc>=1.25.0" \
    "opentelemetry-instrumentation-httpx>=0.46b0" \
    "opentelemetry-instrumentation-starlette>=0.46b0" \
    "opentelemetry-instrumentation-openai-v2>=2.0b0" \
    "opentelemetry-instrumentation-openai>=0.35.0b0"

COPY src/ /app

ENV PYTHONUNBUFFERED=1
ENV WORKSPACE_DIR=/workspace
RUN mkdir -p /workspace

EXPOSE 8000
CMD ["python", "__main__.py", "--host", "0.0.0.0", "--port", "8000"]
