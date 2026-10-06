FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# 1. Instalar OpenJDK 17 (necesario para PySpark)
RUN apt-get update && apt-get install -y default-jre-headless && rm -rf /var/lib/apt-get/lists/*

# 2. Copiar definición de dependencias
COPY pyproject.toml uv.lock README.md ./

# 3. Instalar dependencias e incluir PySpark explícitamente con uv
RUN uv pip install --system pyspark pymongo

# 4. Copiar el código del proyecto
COPY . /app

CMD ["uv", "run", "python", "app.py"]