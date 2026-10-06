# Jenkins with uv installed. The pipeline only needs uv: it downloads Python 3.13
# (.python-version) and installs the locked dependencies (uv.lock) by itself.
FROM jenkins/jenkins:lts-jdk21

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
