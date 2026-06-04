FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV NPTMPL_STORE_PATH=/app/store

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY . .

RUN uv pip install --system .

EXPOSE 9090

VOLUME ["/app/store"]

ENTRYPOINT ["nptmpl", "serve", "--host", "0.0.0.0", "--port", "9090", "--storage", "/app/store"]
