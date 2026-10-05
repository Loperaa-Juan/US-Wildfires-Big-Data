"""
Main PySpark analysis application for US Wildfires dataset.
Runs inside Docker container connected to MongoDB.
"""

import os
import sys
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def create_spark_session() -> SparkSession:
    return (
        SparkSession.builder.appName("USWildfiresSparkAnalysis")
        .master("local[*]")
        .config(
            "spark.jars.packages",
            "org.mongodb.spark:mongo-spark-connector_2.12:10.4.0",
        )
        .config(
            "spark.mongodb.read.connection.uri",
            "mongodb://mongo:27017/wildfires.fires",
        )
        .config("spark.driver.memory", "4g")
        .getOrCreate()
    )


def main():
    print("Iniciando SparkSession dentro del contenedor Docker...")
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    try:
        print("\n[1/4] Leyendo datos GeoJSON desde MongoDB con PySpark...")
        # Leemos permitiendo la inferencia de esquema
        df_raw = spark.read.format("mongodb").load()

        total_records = df_raw.count()
        print(f"\n[2/4] Conteo total de registros procesados por Spark: {total_records:,}")

        print("\n[3/4] Aplanando el objeto GeoJSON 'properties'...")
        if "properties" in df_raw.columns:
            df_flat = df_raw.select("properties.*")
        else:
            df_flat = df_raw

        # Mapeamos nombres de columnas a minúsculas para unificar
        for col_name in df_flat.columns:
            df_flat = df_flat.withColumnRenamed(col_name, col_name.lower())

        print("\n[4/4] Ejecutando agregaciones distribuidas con PySpark:")

        # Identificar dinámicamente las columnas disponibles
        cols = df_flat.columns

        # 1. Agregación por Año
        year_col = next((c for c in ["fire_year", "year"] if c in cols), None)
        if year_col:
            print(f"\n--- Top 5 Años con mayor número de incendios ({year_col}) ---")
            df_flat.filter(F.col(year_col).isNotNull()) \
                   .groupBy(year_col).count() \
                   .orderBy(F.col("count").desc()).show(5)

        # 2. Agregación por Estado
        state_col = next((c for c in ["state", "st"] if c in cols), None)
        if state_col:
            print(f"\n--- Top 10 Estados con más incendios ({state_col}) ---")
            df_flat.filter(F.col(state_col).isNotNull()) \
                   .groupBy(state_col).count() \
                   .orderBy(F.col("count").desc()).show(10)

        # 3. Agregación por Causa
        cause_col = next((c for c in ["stat_cause_descr", "nwcg_general_cause", "cause"] if c in cols), None)
        if cause_col:
            print(f"\n--- Top 10 Causas Principales de Incendios ({cause_col}) ---")
            df_flat.filter(F.col(cause_col).isNotNull()) \
                   .groupBy(cause_col).count() \
                   .orderBy(F.col("count").desc()).show(10, truncate=False)

        # 4. Promedio de Área Quemada
        size_col = next((c for c in ["fire_size", "shape_area"] if c in cols), None)
        if state_col and size_col:
            print(f"\n--- Promedio de Área Quemada (acres) por Top 5 Estados ({size_col}) ---")
            df_flat.filter(F.col(state_col).isNotNull() & F.col(size_col).isNotNull()) \
                   .groupBy(state_col).agg(
                       F.count("*").alias("total_incendios"),
                       F.round(F.avg(size_col), 2).alias("avg_acres_burned"),
                       F.round(F.sum(size_col), 2).alias("total_acres_burned")
                   ).orderBy(F.col("total_incendios").desc()).show(5)

        print("\n¡Análisis directo con PySpark completado con éxito!")

    except Exception as e:
        print(f"\nError durante la ejecución en PySpark: {e}")
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()