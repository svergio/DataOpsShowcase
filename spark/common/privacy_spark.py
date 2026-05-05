"""Shared Spark helpers for privacy: stable hash and non-reversible masks."""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def stable_customer_hash_expr(natural_parts: list[F.Column], salt_literal: str) -> F.Column:
    concat = F.concat_ws("||", *[F.coalesce(c.cast("string"), F.lit("")) for c in natural_parts])
    salted = F.concat_ws("||", concat, F.lit(salt_literal))
    return F.sha2(salted, 256)


def masked_email_col(email_col: F.Column) -> F.Column:
    local = F.split(F.lower(F.trim(email_col)), "@").getItem(0)
    domain = F.split(F.lower(F.trim(email_col)), "@").getItem(1)
    prefix = F.substring(local, 1, 2)
    return F.when(
        email_col.isNull() | (F.trim(email_col) == ""),
        F.lit(None).cast("string"),
    ).otherwise(F.concat_ws("@", F.concat(prefix, F.lit("***")), domain))


def masked_name_col(name_col: F.Column) -> F.Column:
    first = F.trim(F.split(name_col, " ").getItem(0))
    return F.when(
        name_col.isNull() | (F.trim(name_col) == ""),
        F.lit(None).cast("string"),
    ).otherwise(F.concat(F.substring(first, 1, 1), F.lit("***")))
