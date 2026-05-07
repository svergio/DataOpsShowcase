from __future__ import annotations

from airflow.datasets import Dataset

DS_RAW_OLTP = Dataset("postgres://postgres_dwh/raw/oltp")
DS_RAW_KAFKA_ORDERS = Dataset("postgres://postgres_dwh/raw/kafka_orders")
DS_RAW_KAFKA_PAYMENTS = Dataset("postgres://postgres_dwh/raw/kafka_payments")
DS_RAW_MINIO_FILES = Dataset("postgres://postgres_dwh/raw/minio_files")
DS_RAW_KAFKA_EXTENSIONS = Dataset("postgres://postgres_dwh/raw/kafka_extensions")

DS_STG_CLEAN = Dataset("postgres://postgres_dwh/staging/clean")

DS_VAULT_LOADED = Dataset("postgres://postgres_dwh/vault/loaded")
DS_VAULT_SCD2_DONE = Dataset("postgres://postgres_dwh/vault/scd2")

DS_DBT_STAGING_DONE = Dataset("dbt://staging")
DS_DBT_VAULT_DONE = Dataset("dbt://vault")
DS_DBT_MARTS_DONE = Dataset("dbt://marts")
DS_DBT_BUSINESS_KPIS_DONE = Dataset("dbt://business_kpis")
DS_DBT_DQC_DONE = Dataset("dbt://dqc")

DS_DQ_PASSED = Dataset("dq://post-marts")
DS_SERVING_OPTIMIZED = Dataset("serving://marts-optimized")
DS_SPARK_ANALYTICS_DONE = Dataset("spark://analytics-summary")
DS_SPARK_HIVE_FINANCE_DONE = Dataset("spark://hive-finance-cbr-demo")
DS_ML_TRAIN_DONE = Dataset("ml://spark-training")
