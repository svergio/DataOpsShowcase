from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.common.config_loader import load_yaml
from services.common.logging_utils import get_logger
from services.storage.postgres_io import execute, execute_sequence, fetch_one

logger = get_logger(__name__)
DWH_CONN_ID = "postgres_dwh"


@dataclass
class LoadStats:
    name: str
    inserted: int
    updated: int = 0


def _record_source(default: str, override: str | None = None) -> str:
    return override or default


def _vault_config() -> dict[str, Any]:
    return load_yaml("datavault")


_HUB_COLUMNS = {
    "hub_customers": ("customer_hk", "customer_bk"),
    "hub_orders": ("order_hk", "order_bk"),
}


def load_hub(name: str, *, conn_id: str = DWH_CONN_ID) -> LoadStats:
    cfg = _vault_config()
    hub_cfg = cfg["hubs"][name]
    record_source = _record_source(
        cfg.get("record_source_default", "dataops"), hub_cfg.get("record_source_value")
    )
    if name not in _HUB_COLUMNS:
        raise ValueError(f"unsupported hub {name}")
    hk_column, bk_column = _HUB_COLUMNS[name]
    bk_source_col = hub_cfg["business_key"]
    sql = f"""
        WITH ranked AS (
            SELECT DISTINCT
                ENCODE(SHA256(CONVERT_TO(CAST({bk_source_col} AS TEXT), 'UTF8')), 'hex') AS hk,
                CAST({bk_source_col} AS TEXT) AS bk
            FROM {hub_cfg['source']}
            WHERE {bk_source_col} IS NOT NULL
        )
        INSERT INTO vault.{name} ({hk_column}, {bk_column}, load_dts, record_source)
        SELECT hk, bk, NOW(), %s FROM ranked
        ON CONFLICT ({hk_column}) DO NOTHING
    """
    inserted = execute(conn_id, sql, (record_source,))
    logger.info(
        "hub loaded",
        extra={"extra_payload": {"hub": name, "inserted": inserted}},
    )
    return LoadStats(name=name, inserted=inserted)


def load_link(name: str, *, conn_id: str = DWH_CONN_ID) -> LoadStats:
    cfg = _vault_config()
    link_cfg = cfg["links"][name]
    record_source = _record_source(cfg.get("record_source_default", "dataops"), link_cfg.get("record_source_value"))
    if name != "link_customer_orders":
        raise ValueError(f"unsupported link {name}")
    sql = """
        INSERT INTO vault.link_customer_orders (link_hk, customer_hk, order_hk, load_dts, record_source)
        SELECT
            ENCODE(SHA256(CONVERT_TO(
                CAST(customer_id AS TEXT) || '||' || CAST(order_id AS TEXT), 'UTF8'
            )), 'hex'),
            ENCODE(SHA256(CONVERT_TO(CAST(customer_id AS TEXT), 'UTF8')), 'hex'),
            ENCODE(SHA256(CONVERT_TO(CAST(order_id AS TEXT), 'UTF8')), 'hex'),
            NOW(),
            %s
        FROM staging.stg_orders
        WHERE customer_id IS NOT NULL AND order_id IS NOT NULL
        ON CONFLICT (link_hk) DO NOTHING
    """
    inserted = execute(conn_id, sql, (record_source,))
    logger.info(
        "link loaded",
        extra={"extra_payload": {"link": name, "inserted": inserted}},
    )
    return LoadStats(name=name, inserted=inserted)


def load_satellite_scd2(name: str, *, conn_id: str = DWH_CONN_ID) -> LoadStats:
    cfg = _vault_config()
    sat_cfg = cfg["satellites"][name]
    record_source = _record_source(
        cfg.get("record_source_default", "dataops"), sat_cfg.get("record_source_value")
    )
    if name == "sat_customer_details":
        return _load_sat_customer_details(record_source, conn_id)
    if name == "sat_order_status":
        return _load_sat_order_status(record_source, conn_id)
    raise ValueError(f"unsupported satellite {name}")


def _load_sat_customer_details(record_source: str, conn_id: str) -> LoadStats:
    incoming_sql = """
        DROP TABLE IF EXISTS tmp_sat_customer_inbox;
        CREATE TEMP TABLE tmp_sat_customer_inbox AS
        SELECT
            ENCODE(SHA256(CONVERT_TO(CAST(customer_id AS TEXT), 'UTF8')), 'hex') AS customer_hk,
            COALESCE(registered_at, NOW()) AS effective_from,
            ENCODE(SHA256(CONVERT_TO(
                COALESCE(customer_hash, '') || '||' || COALESCE(masked_email, '') || '||' || COALESCE(masked_name, ''),
                'UTF8'
            )), 'hex') AS hash_diff,
            customer_hash,
            masked_email,
            masked_name
        FROM staging.stg_customers
        WHERE customer_id IS NOT NULL AND customer_hash IS NOT NULL;
    """
    close_sql = """
        UPDATE vault.sat_customer_details s
        SET effective_to = inbox.effective_from,
            is_current = FALSE
        FROM tmp_sat_customer_inbox inbox
        WHERE s.customer_hk = inbox.customer_hk
          AND s.is_current = TRUE
          AND s.hash_diff <> inbox.hash_diff
          AND s.effective_from < inbox.effective_from;
    """
    insert_sql = """
        INSERT INTO vault.sat_customer_details (
            customer_hk, load_dts, effective_from, effective_to, is_current,
            hash_diff, customer_hash, masked_email, masked_name, record_source
        )
        SELECT inbox.customer_hk,
               NOW() AS load_dts,
               inbox.effective_from,
               NULL,
               TRUE,
               inbox.hash_diff,
               inbox.customer_hash,
               inbox.masked_email,
               inbox.masked_name,
               %s
        FROM tmp_sat_customer_inbox inbox
        LEFT JOIN vault.sat_customer_details existing
               ON existing.customer_hk = inbox.customer_hk
              AND existing.is_current = TRUE
        WHERE existing.customer_hk IS NULL OR existing.hash_diff <> inbox.hash_diff
        ON CONFLICT (customer_hk, load_dts) DO NOTHING;
    """
    counts = execute_sequence(
        conn_id,
        [(incoming_sql, None), (close_sql, None), (insert_sql, (record_source,))],
    )
    inserted = counts[2]
    return LoadStats(name="sat_customer_details", inserted=inserted)


def _load_sat_order_status(record_source: str, conn_id: str) -> LoadStats:
    incoming_sql = """
        DROP TABLE IF EXISTS tmp_sat_order_inbox;
        CREATE TEMP TABLE tmp_sat_order_inbox AS
        SELECT
            ENCODE(SHA256(CONVERT_TO(CAST(order_id AS TEXT), 'UTF8')), 'hex') AS order_hk,
            order_ts AS effective_from,
            ENCODE(SHA256(CONVERT_TO(status || '||' || CAST(total_amount AS TEXT) || '||' || currency_code, 'UTF8')), 'hex') AS hash_diff,
            status,
            total_amount,
            currency_code
        FROM staging.stg_orders
        WHERE order_id IS NOT NULL;
    """
    close_sql = """
        UPDATE vault.sat_order_status s
        SET effective_to = inbox.effective_from,
            is_current = FALSE
        FROM tmp_sat_order_inbox inbox
        WHERE s.order_hk = inbox.order_hk
          AND s.is_current = TRUE
          AND s.hash_diff <> inbox.hash_diff
          AND s.effective_from < inbox.effective_from;
    """
    insert_sql = """
        INSERT INTO vault.sat_order_status (
            order_hk, load_dts, effective_from, effective_to, is_current,
            hash_diff, status, total_amount, currency, record_source
        )
        SELECT inbox.order_hk,
               NOW(),
               inbox.effective_from,
               NULL,
               TRUE,
               inbox.hash_diff,
               inbox.status,
               inbox.total_amount,
               inbox.currency_code,
               %s
        FROM tmp_sat_order_inbox inbox
        LEFT JOIN vault.sat_order_status existing
               ON existing.order_hk = inbox.order_hk
              AND existing.is_current = TRUE
        WHERE existing.order_hk IS NULL OR existing.hash_diff <> inbox.hash_diff
        ON CONFLICT (order_hk, load_dts) DO NOTHING;
    """
    counts = execute_sequence(
        conn_id,
        [(incoming_sql, None), (close_sql, None), (insert_sql, (record_source,))],
    )
    inserted = counts[2]
    return LoadStats(name="sat_order_status", inserted=inserted)


def reconcile_late_arriving(satellite: str, *, conn_id: str = DWH_CONN_ID) -> int:
    """
    Reconcile late-arriving rows: when an event with effective_from earlier
    than an already-current satellite version appears, we insert it as a
    historical version preserving SCD2 chain integrity.
    """
    if satellite == "sat_customer_details":
        sql = """
            WITH late AS (
                SELECT
                    s.customer_hk,
                    s.effective_from,
                    s.hash_diff,
                    LEAD(s.effective_from) OVER (PARTITION BY s.customer_hk ORDER BY s.effective_from) AS next_from
                FROM vault.sat_customer_details s
            )
            UPDATE vault.sat_customer_details s
            SET effective_to = late.next_from,
                is_current = FALSE
            FROM late
            WHERE s.customer_hk = late.customer_hk
              AND s.effective_from = late.effective_from
              AND late.next_from IS NOT NULL
              AND (s.effective_to IS DISTINCT FROM late.next_from OR s.is_current = TRUE);
        """
    elif satellite == "sat_order_status":
        sql = """
            WITH late AS (
                SELECT
                    s.order_hk,
                    s.effective_from,
                    s.hash_diff,
                    LEAD(s.effective_from) OVER (PARTITION BY s.order_hk ORDER BY s.effective_from) AS next_from
                FROM vault.sat_order_status s
            )
            UPDATE vault.sat_order_status s
            SET effective_to = late.next_from,
                is_current = FALSE
            FROM late
            WHERE s.order_hk = late.order_hk
              AND s.effective_from = late.effective_from
              AND late.next_from IS NOT NULL
              AND (s.effective_to IS DISTINCT FROM late.next_from OR s.is_current = TRUE);
        """
    else:
        raise ValueError(f"unsupported satellite {satellite}")
    rows = execute(conn_id, sql)
    logger.info(
        "scd2 late-arriving reconciliation",
        extra={"extra_payload": {"satellite": satellite, "rows_affected": rows}},
    )
    return rows


def vault_summary(conn_id: str = DWH_CONN_ID) -> dict[str, int]:
    summary = {}
    for table in [
        "vault.hub_customers",
        "vault.hub_orders",
        "vault.link_customer_orders",
        "vault.sat_customer_details",
        "vault.sat_order_status",
    ]:
        row = fetch_one(conn_id, f"SELECT COUNT(*) FROM {table}")
        summary[table] = int(row[0]) if row else 0
    return summary
