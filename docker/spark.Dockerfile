FROM python:3.11-slim-bookworm

WORKDIR /app

# Instalar OpenJDK 17 y herramientas necesarias
RUN apt-get update && apt-get install -y default-jre-headless procps curl && rm -rf /var/lib/apt-get/lists/*

# Copiar archivos de configuración
COPY pyproject.toml README.md ./

# Instalar PySpark y PyMongo en el entorno de Python 3.11
RUN pip install --no-cache-dir pyspark==3.5.1 pymongo

# Copiar el código del proyecto
COPY . /app

# The package lives in src/ and is not installed, so put it on the import path
ENV PYTHONPATH=/app/src

CMD ["python", "-m", "us_wildfires_big_data.spark.analysis"]
