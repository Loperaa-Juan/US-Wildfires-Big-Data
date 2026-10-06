# Image for the Spark stage. Same Python and locked dependencies as the Dask image, plus the
# `spark` extra (pyspark) and the Java runtime that Spark needs (Spark 4 requires Java 17+).
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Debian bookworm's default JRE is OpenJDK 17; procps provides `ps`, used by Spark's scripts
RUN apt-get update \
    && apt-get install -y --no-install-recommends default-jre-headless procps \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Dependencies first, so this layer is cached while only the code changes
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --extra spark --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev --extra spark

CMD ["python", "-m", "us_wildfires_big_data.spark.analysis"]
