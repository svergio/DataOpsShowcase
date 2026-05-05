from __future__ import annotations

from airflow.datasets import Dataset
from airflow.models import Variable

from pipelines.utils.datasets import (
    DS_RAW_KAFKA_ORDERS,
    DS_RAW_KAFKA_PAYMENTS,
    DS_RAW_MINIO_FILES,
    DS_RAW_OLTP,
)


def raw_four_tuple() -> tuple[Dataset, Dataset, Dataset, Dataset]:
    return (
        DS_RAW_OLTP,
        DS_RAW_KAFKA_ORDERS,
        DS_RAW_KAFKA_PAYMENTS,
        DS_RAW_MINIO_FILES,
    )


def spark_preprocess_schedule() -> Dataset:
    try:
        mode = str(Variable.get("spark_preprocess_mode", default_var="all_raw")).strip().lower()
    except Exception:  # noqa: BLE001
        mode = "all_raw"
    a, b, c, d = raw_four_tuple()
    if mode == "any_raw":
        return a | b | c | d
    return a & b & c & d
