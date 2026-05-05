#!/usr/bin/env python3

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("superset_bootstrap")

DW_SCHEMA = "dwh_marts"
DB_NAME = os.getenv("TECHMART_SUPERSET_DATABASE_LABEL", "TechMart DWH")

SLUG_BUSINESS_OVERVIEW = "techmart-business-overview"
SLUG_PRODUCT_ANALYTICS = "techmart-product-analytics"
SLUG_CUSTOMER_SALES = "techmart-customer-sales-analysis"
SLUG_FINANCE_DEMO = "techmart-finansy-hive-demo"

FINANCE_DEMO_SCHEMA = "demo_fin"

DATASET_TABLES: tuple[str, ...] = (
    "dim_customers",
    "dim_products",
    "fct_orders",
    "fct_daily_sales",
    "redis_serving_snapshot",
)

FINANCE_DATASET_TABLES: tuple[str, ...] = (
    "mart_daily_finance_rub",
    "mart_order_mix_rub",
)

MAIN_DTTM: dict[str, str] = {
    "dim_customers": "registered_at",
    "fct_daily_sales": "order_date",
    "fct_orders": "order_ts",
    "redis_serving_snapshot": "updated_at",
    "mart_daily_finance_rub": "order_date",
    "mart_order_mix_rub": "order_date",
}


def _dashboard_json_metadata(merge_from: str | None) -> str:
    base: dict[str, Any] = {
        "chart_configuration": {},
        "label_colors": {},
        "native_filter_configuration": [],
        "timed_filter_configuration": [],
        "cross_filters_enabled": False,
        "global_chart_configuration": {},
        "map_label_colors": {},
    }
    if merge_from and str(merge_from).strip():
        try:
            parsed = json.loads(merge_from)
            if isinstance(parsed, dict):
                # Stale chart_configuration / global_chart_configuration can crash the UI (undefined theme.background).
                for key in (
                    "label_colors",
                    "map_label_colors",
                ):
                    val = parsed.get(key)
                    if isinstance(val, dict) and val:
                        base[key] = val
        except json.JSONDecodeError:
            pass
    return json.dumps(base)


def _dwh_uri() -> str:
    uri = os.getenv("SUPERSET_DWH_DATABASE_URI", "").strip()
    if uri:
        return uri
    user = os.getenv("SUPERSET_DWH_PG_USER", os.getenv("PG_OLAP_USER", "olap_user"))
    pw = os.getenv("SUPERSET_DWH_PG_PASSWORD", os.getenv("PG_OLAP_PASSWORD", "olap_pass"))
    host = os.getenv("SUPERSET_DWH_PG_HOST", "postgres_olap")
    name = os.getenv("SUPERSET_DWH_PG_DB", os.getenv("PG_OLAP_DB", "techmart_dwh"))
    port = os.getenv("SUPERSET_DWH_PG_PORT", "5432")
    return f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{name}"


@dataclass(frozen=True)
class ChartLayout:
    row_id: str
    charts: tuple[tuple[str, str, int, int], ...]


def _bootstrap_inner() -> None:
    from superset import security_manager
    from superset.commands.database.create import CreateDatabaseCommand
    from superset.commands.database.exceptions import DatabaseInvalidError
    from superset.commands.dataset.create import CreateDatasetCommand
    from superset.commands.dataset.exceptions import DatasetInvalidError
    from superset.connectors.sqla.models import SqlaTable
    from superset.examples.helpers import get_slice_json, merge_slice, update_slice_ids
    from superset.extensions import db
    from superset.models.core import Database
    from superset.models.dashboard import Dashboard
    from superset.models.slice import Slice
    from superset.utils.core import DatasourceType
    from sqlalchemy import inspect as sa_inspect

    def physical_table_exists(database: Database, table_name: str, *, schema: str = DW_SCHEMA) -> bool:
        try:
            with database.get_sqla_engine() as eng:
                return bool(sa_inspect(eng).has_table(table_name, schema=schema))
        except Exception:
            logger.warning(
                "Could not inspect database for table %s.%s",
                schema,
                table_name,
                exc_info=True,
            )
            return False

    def ensure_owner():
        username = os.getenv(
            "SUPERSET_ADMIN_USERNAME",
            os.getenv("SUPERSET_ADMIN_USER", "admin"),
        )
        user = security_manager.find_user(username=username)
        if not user:
            raise RuntimeError(f"FAB user not found: {username}")
        return user

    def ensure_database_connection() -> Database:
        uri = _dwh_uri()
        existing = db.session.query(Database).filter_by(database_name=DB_NAME).one_or_none()
        if existing:
            if (existing.sqlalchemy_uri or "").strip() != uri.strip():
                existing.sqlalchemy_uri = uri
                db.session.commit()
                logger.info("Updated SQLAlchemy URI for database %s id=%s", DB_NAME, existing.id)
            else:
                logger.info("Database %s exists id=%s", DB_NAME, existing.id)
            return existing
        try:
            db_obj = CreateDatabaseCommand(
                {
                    "database_name": DB_NAME,
                    "sqlalchemy_uri": uri,
                    "expose_in_sqllab": True,
                    "allow_ctas": False,
                    "allow_cvas": False,
                    "allow_dml": False,
                    "extra": "{}",
                }
            ).run()
            db.session.commit()
            logger.info("Created database connection %s", DB_NAME)
            return db_obj
        except DatabaseInvalidError:
            logger.exception("Cannot create OLAP database entry")
            raise

    def ensure_dataset(
        database: Database,
        table_name: str,
        owner,
        *,
        schema: str = DW_SCHEMA,
        placeholder_hint: str = "OLAP table missing; run dbt marts then re-bootstrap",
    ) -> SqlaTable | None:
        exists = (
            db.session.query(SqlaTable)
            .filter_by(
                database_id=database.id,
                schema=schema,
                table_name=table_name,
            )
            .first()
        )
        has_table = physical_table_exists(database, table_name, schema=schema)

        if exists:
            if has_table:
                try:
                    if table_name in MAIN_DTTM:
                        exists.main_dttm_col = MAIN_DTTM[table_name]
                    exists.fetch_metadata()
                    db.session.commit()
                    logger.info("Refreshed dataset id=%s %s.%s", exists.id, schema, table_name)
                except Exception:
                    logger.warning(
                        "Dataset %s.%s metadata refresh failed",
                        schema,
                        table_name,
                        exc_info=True,
                    )
                    db.session.rollback()
            else:
                logger.info(
                    "Dataset id=%s %s.%s is placeholder until physical table exists",
                    exists.id,
                    schema,
                    table_name,
                )
            return exists

        if has_table:
            try:
                ds = CreateDatasetCommand(
                    {
                        "database": database.id,
                        "schema": schema,
                        "table_name": table_name,
                        "owners": [owner.id],
                    }
                ).run()
                sid = ds.id
                db.session.commit()
                tbl = db.session.query(SqlaTable).filter_by(id=sid).one()
                if table_name in MAIN_DTTM:
                    tbl.main_dttm_col = MAIN_DTTM[table_name]
                tbl.fetch_metadata()
                db.session.commit()
                db.session.refresh(tbl)
                ncols = len(tbl.columns) if tbl.columns is not None else 0
                logger.info(
                    "Registered dataset id=%s %s.%s columns=%s",
                    sid,
                    schema,
                    table_name,
                    ncols,
                )
                return tbl
            except DatasetInvalidError as ex:
                detail = [str(e) for e in getattr(ex, "_exceptions", ())] or [str(ex)]
                logger.warning(
                    "Dataset %s invalid: %s",
                    table_name,
                    "; ".join(detail),
                )
                db.session.rollback()
            except Exception:
                logger.exception("Dataset %s not available.", table_name)
                db.session.rollback()
            return None

        ds = SqlaTable(
            database_id=database.id,
            schema=schema,
            table_name=table_name,
        )
        if table_name in MAIN_DTTM:
            ds.main_dttm_col = MAIN_DTTM[table_name]
        ds.owners = [owner]
        db.session.add(ds)
        db.session.commit()
        logger.info(
            "Placeholder dataset id=%s %s.%s (%s)",
            ds.id,
            schema,
            table_name,
            placeholder_hint,
        )
        return ds

    def ensure_chart_slice(
        owner,
        slice_name: str,
        viz_type: str,
        datasource_id: int,
        slice_kwargs: dict[str, Any],
    ) -> None:
        base: dict[str, Any] = {
            "datasource": f"{datasource_id}__table",
            "viz_type": viz_type,
        }
        params = get_slice_json(base, **slice_kwargs)
        sl = Slice(
            slice_name=slice_name,
            viz_type=viz_type,
            params=params,
            datasource_id=datasource_id,
            datasource_type=DatasourceType.TABLE.value,
            owners=[owner],
        )
        merge_slice(sl)
        db.session.commit()

    def _intro_block(title: str, body_html: str, slug: str) -> str:
        return (
            f"<div style='padding:10px'><h2>{title}</h2>{body_html}"
            f"<p><small>Slug: <code>/superset/dashboard/{slug}/</code> &middot; "
            f"Схема Postgres: <code>{DW_SCHEMA}</code> &middot; "
            f"При изменении витрин перезапустите bootstrap.</small></p></div>"
        )

    def _intro_block_finance_demo(title: str, body_html: str, slug: str) -> str:
        return (
            f"<div style='padding:10px'><h2>{title}</h2>{body_html}"
            f"<p><small>Slug: <code>/superset/dashboard/{slug}/</code> &middot; "
            f"Схема Postgres: <code>{FINANCE_DEMO_SCHEMA}</code> &middot; "
            f"Данные из DAG <code>dag_spark_hive_finance_cbr_demo</code> (Spark + SOAP ЦБ + JDBC в Postgres). "
            f"Slug с «hive» — для стабильности URL; без Hive metastore.</small></p></div>"
        )

    def _apply_grid_layout(
        position: dict,
        grid_children: list[str],
        layouts: Iterable[ChartLayout],
    ) -> list[str]:
        slice_names: list[str] = []
        for layout in layouts:
            grid_children.append(layout.row_id)
            ch_ids = [c[0] for c in layout.charts]
            position[layout.row_id] = {
                "type": "ROW",
                "id": layout.row_id,
                "children": ch_ids,
                "parents": ["ROOT_ID", "GRID_ID"],
            }
            for ch_id, sname, height, width in layout.charts:
                slice_names.append(sname)
                position[ch_id] = {
                    "type": "CHART",
                    "id": ch_id,
                    "parents": ["ROOT_ID", "GRID_ID", layout.row_id],
                    "children": [],
                    "meta": {
                        "chartId": 1,
                        "sliceName": sname,
                        "height": height,
                        "width": width,
                    },
                }
        return slice_names

    def _base_position(intro_html: str, md_height: int) -> tuple[dict, list[str]]:
        grid_children: list[str] = ["ROW_MD"]
        position: dict[str, Any] = {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {
                "type": "GRID",
                "id": "GRID_ID",
                "children": grid_children,
                "parents": ["ROOT_ID"],
            },
            "ROW_MD": {
                "type": "ROW",
                "id": "ROW_MD",
                "meta": {},
                "children": ["MD1"],
                "parents": ["ROOT_ID", "GRID_ID"],
            },
            "MD1": {
                "type": "MARKDOWN",
                "id": "MD1",
                "parents": ["ROOT_ID", "GRID_ID", "ROW_MD"],
                "children": [],
                "meta": {"code": intro_html, "width": 12, "height": md_height},
            },
        }
        return position, grid_children

    def ensure_dashboard_with_charts(
        slug: str,
        dashboard_title: str,
        intro_html: str,
        intro_md_height: int,
        layouts: list[ChartLayout],
        chart_builders: list[Callable[[], None]],
    ) -> None:
        for fn in chart_builders:
            fn()
        position, grid_children = _base_position(intro_html, intro_md_height)
        slice_names = _apply_grid_layout(position, grid_children, layouts)
        update_slice_ids(position)
        dash = db.session.query(Dashboard).filter_by(slug=slug).one_or_none()
        slices = [
            db.session.query(Slice).filter_by(slice_name=n).one()
            for n in slice_names
        ]
        pos_json = json.dumps(position)
        if dash:
            dash.dashboard_title = dashboard_title
            dash.position_json = pos_json
            dash.published = True
            dash.slices = slices
            prev_meta = getattr(dash, "json_metadata", None)
            merge_src: str | None
            if isinstance(prev_meta, str):
                merge_src = prev_meta
            elif isinstance(prev_meta, dict):
                merge_src = json.dumps(prev_meta)
            else:
                merge_src = None
            dash.json_metadata = _dashboard_json_metadata(merge_src)
            db.session.commit()
            logger.info("Updated dashboard slug=%s slices=%s", slug, len(slices))
        else:
            owner = ensure_owner()
            dash = Dashboard(
                dashboard_title=dashboard_title,
                slug=slug,
                published=True,
                position_json=pos_json,
                owners=[owner],
                slices=slices,
            )
            dash.json_metadata = _dashboard_json_metadata(None)
            db.session.add(dash)
            db.session.commit()
            logger.info("Created dashboard slug=%s slices=%s", slug, len(slices))

    owner = ensure_owner()
    database = ensure_database_connection()
    orphan = (
        db.session.query(SqlaTable)
        .filter_by(
            database_id=database.id,
            schema=DW_SCHEMA,
            table_name="_bootstrap_probe",
        )
        .first()
    )
    if orphan:
        db.session.delete(orphan)
        db.session.commit()
        logger.info("Removed stray dataset _bootstrap_probe from metadata")

    reg: dict[str, int] = {}
    for t in DATASET_TABLES:
        ds = ensure_dataset(database, t, owner)
        if ds is not None:
            reg[t] = ds.id

    def rid(*parts: str) -> str:
        return "_".join(parts)[:40]

    bo_intro = _intro_block(
        "Бизнес-обзор TechMart",
        "<p>Сводка по витринам <code>dwh_marts</code>: продажи, заказы, Redis serving.</p>",
        SLUG_BUSINESS_OVERVIEW,
    )
    bo_layouts: list[ChartLayout] = []
    bo_builders: list[Callable[[], None]] = []

    if "fct_daily_sales" in reg:
        i = reg["fct_daily_sales"]
        bo_layouts.append(
            ChartLayout(
                rid("BO", "r1"),
                (
                    (rid("BO", "c1a"), "RU_BO_KPI_Sum_Gross_Sales", 32, 6),
                    (rid("BO", "c1b"), "RU_BO_KPI_Order_Days", 32, 6),
                ),
            )
        )
        bo_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_BO_KPI_Sum_Gross_Sales",
                "big_number_total",
                i,
                {"metric": "sum__gross_sales"},
            )
        )
        bo_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_BO_KPI_Order_Days",
                "big_number_total",
                i,
                {"metric": "count"},
            )
        )
        bo_layouts.append(
            ChartLayout(
                rid("BO", "r2"),
                ((rid("BO", "c2"), "RU_BO_Line_Gross_Sales_By_Day", 48, 12),),
            )
        )
        bo_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_BO_Line_Gross_Sales_By_Day",
                "echarts_timeseries_line",
                i,
                {
                    "time_range": "No filter",
                    "row_limit": 100000,
                    "granularity_sqla": "order_date",
                    "metrics": ["sum__gross_sales"],
                },
            )
        )

    if "fct_orders" in reg:
        i = reg["fct_orders"]
        bo_layouts.append(
            ChartLayout(
                rid("BO", "r3"),
                ((rid("BO", "c3"), "RU_BO_Bar_Orders_By_Currency", 44, 12),),
            )
        )
        bo_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_BO_Bar_Orders_By_Currency",
                "bar",
                i,
                {"groupby": ["currency"], "metrics": ["count"], "row_limit": 100},
            )
        )

    if "redis_serving_snapshot" in reg:
        i = reg["redis_serving_snapshot"]
        bo_layouts.append(
            ChartLayout(
                rid("BO", "r4"),
                (
                    (rid("BO", "c4a"), "RU_BO_Table_Redis_KPIs", 40, 7),
                    (rid("BO", "c4b"), "RU_BO_Bar_Redis_Metric_Values", 40, 5),
                ),
            )
        )
        bo_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_BO_Table_Redis_KPIs",
                "table",
                i,
                {
                    "row_limit": 100,
                    "all_columns": [
                        "metric_key",
                        "metric_value_num",
                        "metric_value_text",
                        "updated_at",
                    ],
                },
            )
        )
        bo_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_BO_Bar_Redis_Metric_Values",
                "bar",
                i,
                {"groupby": ["metric_key"], "metrics": ["sum__metric_value_num"], "row_limit": 50},
            )
        )

    if len(bo_layouts) < 4 and "fct_orders" in reg:
        i = reg["fct_orders"]
        bo_layouts.append(
            ChartLayout(
                rid("BO", "r6"),
                ((rid("BO", "c6"), "RU_BO_Bar_Orders_Payment_State", 44, 12),),
            )
        )
        bo_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_BO_Bar_Orders_Payment_State",
                "bar",
                i,
                {"groupby": ["payment_state"], "metrics": ["count"], "row_limit": 50},
            )
        )

    if len(bo_layouts) < 4 and "dim_products" in reg:
        i = reg["dim_products"]
        bo_layouts.append(
            ChartLayout(
                rid("BO", "r7"),
                ((rid("BO", "c7"), "RU_BO_Pie_Product_Categories", 44, 12),),
            )
        )
        bo_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_BO_Pie_Product_Categories",
                "pie",
                i,
                {"groupby": ["category"], "metric": "count", "row_limit": 200},
            )
        )

    if not bo_layouts:
        bo_intro = _intro_block(
            "Бизнес-обзор TechMart",
            "<p><b>Витрины ещё не готовы.</b> Запустите цепочку dbt до <code>dwh_marts</code> "
            "(например <code>dag_dbt_marts_rest</code>) и при необходимости <code>dag_serving_optimizations</code>.</p>",
            SLUG_BUSINESS_OVERVIEW,
        )

    ensure_dashboard_with_charts(
        SLUG_BUSINESS_OVERVIEW,
        "Бизнес-обзор TechMart",
        bo_intro,
        26,
        bo_layouts,
        bo_builders,
    )

    pa_intro = _intro_block(
        "Продуктовая аналитика",
        "<p>Каталог, категории, динамика продаж и заказы; срез клиентов по <code>dim_customers</code>.</p>",
        SLUG_PRODUCT_ANALYTICS,
    )
    pa_layouts: list[ChartLayout] = []
    pa_builders: list[Callable[[], None]] = []

    if "dim_products" in reg:
        i = reg["dim_products"]
        pa_layouts.append(
            ChartLayout(
                rid("PA", "r1"),
                (
                    (rid("PA", "c1a"), "RU_PA_KPI_Active_Products", 30, 6),
                    (rid("PA", "c1b"), "RU_PA_KPI_Avg_Price", 30, 6),
                ),
            )
        )
        pa_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_PA_KPI_Active_Products",
                "big_number_total",
                i,
                {"metric": "count"},
            )
        )
        pa_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_PA_KPI_Avg_Price",
                "big_number_total",
                i,
                {"metric": "avg__price"},
            )
        )
        pa_layouts.append(
            ChartLayout(
                rid("PA", "r2"),
                ((rid("PA", "c2"), "RU_PA_Pie_Category_Mix", 44, 12),),
            )
        )
        pa_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_PA_Pie_Category_Mix",
                "pie",
                i,
                {"groupby": ["category"], "metric": "count", "row_limit": 200},
            )
        )
        pa_layouts.append(
            ChartLayout(
                rid("PA", "r3"),
                ((rid("PA", "c3"), "RU_PA_Table_Product_Catalog", 50, 12),),
            )
        )
        pa_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_PA_Table_Product_Catalog",
                "table",
                i,
                {
                    "row_limit": 200,
                    "all_columns": [
                        "sku",
                        "product_name",
                        "category",
                        "price",
                        "is_active",
                    ],
                },
            )
        )

    if "fct_daily_sales" in reg:
        i = reg["fct_daily_sales"]
        pa_layouts.append(
            ChartLayout(
                rid("PA", "r4"),
                ((rid("PA", "c4"), "RU_PA_Line_Gross_Sales", 48, 12),),
            )
        )
        pa_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_PA_Line_Gross_Sales",
                "echarts_timeseries_line",
                i,
                {
                    "time_range": "No filter",
                    "row_limit": 100000,
                    "granularity_sqla": "order_date",
                    "metrics": ["sum__gross_sales"],
                },
            )
        )
        pa_layouts.append(
            ChartLayout(
                rid("PA", "r5"),
                ((rid("PA", "c5"), "RU_PA_Bar_Gross_Sales_By_Currency", 44, 12),),
            )
        )
        pa_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_PA_Bar_Gross_Sales_By_Currency",
                "bar",
                i,
                {"groupby": ["currency"], "metrics": ["sum__gross_sales"], "row_limit": 50},
            )
        )

    if "fct_orders" in reg:
        i = reg["fct_orders"]
        pa_layouts.append(
            ChartLayout(
                rid("PA", "r6"),
                ((rid("PA", "c6"), "RU_PA_Bar_Orders_Payment_State", 44, 12),),
            )
        )
        pa_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_PA_Bar_Orders_Payment_State",
                "bar",
                i,
                {"groupby": ["payment_state"], "metrics": ["count"], "row_limit": 50},
            )
        )

    if "dim_customers" in reg:
        dc = reg["dim_customers"]
        pa_layouts.append(
            ChartLayout(
                rid("PA", "r7"),
                ((rid("PA", "c7"), "RU_PA_Pie_Customer_Segment", 44, 12),),
            )
        )
        pa_builders.append(
            lambda dc=dc: ensure_chart_slice(
                owner,
                "RU_PA_Pie_Customer_Segment",
                "pie",
                dc,
                {"groupby": ["customer_segment"], "metric": "count", "row_limit": 200},
            )
        )
        pa_layouts.append(
            ChartLayout(
                rid("PA", "r8"),
                ((rid("PA", "c8"), "RU_PA_Bar_Customers_By_Email_Domain", 44, 12),),
            )
        )
        pa_builders.append(
            lambda dc=dc: ensure_chart_slice(
                owner,
                "RU_PA_Bar_Customers_By_Email_Domain",
                "bar",
                dc,
                {"groupby": ["email_domain"], "metrics": ["count"], "row_limit": 50},
            )
        )

    if not pa_layouts:
        pa_intro = _intro_block(
            "Продуктовая аналитика",
            "<p><b>Витрины не готовы.</b> Соберите <code>dwh_marts.dim_products</code>, "
            "<code>dim_customers</code>, <code>fct_daily_sales</code>, <code>fct_orders</code> через dbt и повторите bootstrap.</p>",
            SLUG_PRODUCT_ANALYTICS,
        )

    ensure_dashboard_with_charts(
        SLUG_PRODUCT_ANALYTICS,
        "Продуктовая аналитика",
        pa_intro,
        24,
        pa_layouts,
        pa_builders,
    )

    cs_intro = _intro_block(
        "Клиенты и продажи",
        "<p>Заказы, оплаты, дневные продажи, Redis; срез клиентов по <code>dim_customers</code>. Без Spark.</p>",
        SLUG_CUSTOMER_SALES,
    )
    cs_layouts: list[ChartLayout] = []
    cs_builders: list[Callable[[], None]] = []

    if "fct_orders" in reg:
        i = reg["fct_orders"]
        cs_layouts.append(
            ChartLayout(
                rid("CS", "r1"),
                (
                    (rid("CS", "c1a"), "RU_CS_KPI_Order_Count", 30, 6),
                    (rid("CS", "c1b"), "RU_CS_KPI_Revenue_Sum", 30, 6),
                ),
            )
        )
        cs_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_CS_KPI_Order_Count",
                "big_number_total",
                i,
                {"metric": "count"},
            )
        )
        cs_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_CS_KPI_Revenue_Sum",
                "big_number_total",
                i,
                {"metric": "sum__total_amount"},
            )
        )
        cs_layouts.append(
            ChartLayout(
                rid("CS", "r2"),
                ((rid("CS", "c2"), "RU_CS_Line_Orders_Per_Day", 48, 12),),
            )
        )
        cs_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_CS_Line_Orders_Per_Day",
                "echarts_timeseries_line",
                i,
                {
                    "time_range": "No filter",
                    "row_limit": 100000,
                    "granularity_sqla": "order_ts",
                    "metrics": ["count"],
                },
            )
        )
        cs_layouts.append(
            ChartLayout(
                rid("CS", "r3"),
                ((rid("CS", "c3"), "RU_CS_Bar_Payment_State", 42, 12),),
            )
        )
        cs_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_CS_Bar_Payment_State",
                "bar",
                i,
                {"groupby": ["payment_state"], "metrics": ["count"], "row_limit": 50},
            )
        )
        cs_layouts.append(
            ChartLayout(
                rid("CS", "r4"),
                ((rid("CS", "c4"), "RU_CS_Table_Recent_Orders", 52, 12),),
            )
        )
        cs_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_CS_Table_Recent_Orders",
                "table",
                i,
                {
                    "row_limit": 100,
                    "order_by_cols": [["order_ts", False]],
                    "all_columns": [
                        "order_bk",
                        "order_date",
                        "total_amount",
                        "currency",
                        "payment_state",
                        "is_high_value",
                    ],
                },
            )
        )

    if "fct_daily_sales" in reg:
        i = reg["fct_daily_sales"]
        cs_layouts.append(
            ChartLayout(
                rid("CS", "r5"),
                ((rid("CS", "c5"), "RU_CS_Area_Paid_Vs_Unpaid", 48, 12),),
            )
        )
        cs_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_CS_Area_Paid_Vs_Unpaid",
                "echarts_timeseries_area",
                i,
                {
                    "time_range": "No filter",
                    "row_limit": 100000,
                    "granularity_sqla": "order_date",
                    "metrics": ["sum__paid_sales", "sum__unpaid_sales"],
                },
            )
        )

    if "redis_serving_snapshot" in reg:
        i = reg["redis_serving_snapshot"]
        cs_layouts.append(
            ChartLayout(
                rid("CS", "r6"),
                ((rid("CS", "c6"), "RU_CS_Bar_Redis_Active_Customers_KPI", 40, 12),),
            )
        )
        cs_builders.append(
            lambda i=i: ensure_chart_slice(
                owner,
                "RU_CS_Bar_Redis_Active_Customers_KPI",
                "bar",
                i,
                {"groupby": ["metric_key"], "metrics": ["max__metric_value_num"], "row_limit": 20},
            )
        )

    if "dim_customers" in reg:
        dc = reg["dim_customers"]
        cs_layouts.append(
            ChartLayout(
                rid("CS", "r7"),
                (
                    (rid("CS", "c7a"), "RU_CS_KPI_Customers_Count", 30, 6),
                    (rid("CS", "c7b"), "RU_CS_KPI_Spend_90d_Sum", 30, 6),
                ),
            )
        )
        cs_builders.append(
            lambda dc=dc: ensure_chart_slice(
                owner,
                "RU_CS_KPI_Customers_Count",
                "big_number_total",
                dc,
                {"metric": "count"},
            )
        )
        cs_builders.append(
            lambda dc=dc: ensure_chart_slice(
                owner,
                "RU_CS_KPI_Spend_90d_Sum",
                "big_number_total",
                dc,
                {"metric": "sum__spend_90d"},
            )
        )
        cs_layouts.append(
            ChartLayout(
                rid("CS", "r8"),
                ((rid("CS", "c8"), "RU_CS_Bar_Customer_Segment", 44, 12),),
            )
        )
        cs_builders.append(
            lambda dc=dc: ensure_chart_slice(
                owner,
                "RU_CS_Bar_Customer_Segment",
                "bar",
                dc,
                {"groupby": ["customer_segment"], "metrics": ["count"], "row_limit": 50},
            )
        )

    if not cs_layouts:
        cs_intro = _intro_block(
            "Клиенты и продажи",
            "<p><b>Нет фактов заказов.</b> Соберите <code>dwh_marts.fct_orders</code> (dbt marts) и повторите bootstrap.</p>",
            SLUG_CUSTOMER_SALES,
        )

    ensure_dashboard_with_charts(
        SLUG_CUSTOMER_SALES,
        "Клиенты и продажи",
        cs_intro,
        24,
        cs_layouts,
        cs_builders,
    )

    reg_fin: dict[str, int] = {}
    for t in FINANCE_DATASET_TABLES:
        ds_f = ensure_dataset(
            database,
            t,
            owner,
            schema=FINANCE_DEMO_SCHEMA,
            placeholder_hint="Сначала dag_spark_hive_finance_cbr_demo, затем bootstrap",
        )
        if ds_f is not None:
            reg_fin[t] = ds_f.id

    hv_intro = _intro_block_finance_demo(
        "Финансы (демо Postgres)",
        "<p>Выручка в рублях по курсу ЦБ (SOAP), дневные агрегаты и структура по валюте и статусу оплаты.</p>",
        SLUG_FINANCE_DEMO,
    )
    hv_layouts: list[ChartLayout] = []
    hv_builders: list[Callable[[], None]] = []

    if "mart_daily_finance_rub" in reg_fin:
        hid = reg_fin["mart_daily_finance_rub"]
        hv_layouts.append(
            ChartLayout(
                rid("HV", "r1"),
                (
                    (rid("HV", "c1a"), "RU_HV_KPI_Gross_Sales_RUB", 30, 6),
                    (rid("HV", "c1b"), "RU_HV_KPI_Order_Count", 30, 6),
                ),
            )
        )
        hv_builders.append(
            lambda hid=hid: ensure_chart_slice(
                owner,
                "RU_HV_KPI_Gross_Sales_RUB",
                "big_number_total",
                hid,
                {"metric": "sum__gross_sales_rub"},
            )
        )
        hv_builders.append(
            lambda hid=hid: ensure_chart_slice(
                owner,
                "RU_HV_KPI_Order_Count",
                "big_number_total",
                hid,
                {"metric": "sum__order_count"},
            )
        )
        hv_layouts.append(
            ChartLayout(
                rid("HV", "r2"),
                ((rid("HV", "c2"), "RU_HV_Line_Gross_Sales_RUB", 48, 12),),
            )
        )
        hv_builders.append(
            lambda hid=hid: ensure_chart_slice(
                owner,
                "RU_HV_Line_Gross_Sales_RUB",
                "echarts_timeseries_line",
                hid,
                {
                    "time_range": "No filter",
                    "row_limit": 100000,
                    "granularity_sqla": "order_date",
                    "metrics": ["sum__gross_sales_rub"],
                },
            )
        )
        hv_layouts.append(
            ChartLayout(
                rid("HV", "r3"),
                ((rid("HV", "c3"), "RU_HV_Bar_Gross_Sales_RUB_By_Currency", 44, 12),),
            )
        )
        hv_builders.append(
            lambda hid=hid: ensure_chart_slice(
                owner,
                "RU_HV_Bar_Gross_Sales_RUB_By_Currency",
                "bar",
                hid,
                {"groupby": ["currency"], "metrics": ["sum__gross_sales_rub"], "row_limit": 100},
            )
        )

    if "mart_order_mix_rub" in reg_fin:
        mid = reg_fin["mart_order_mix_rub"]
        hv_layouts.append(
            ChartLayout(
                rid("HV", "r4"),
                ((rid("HV", "c4"), "RU_HV_Bar_Revenue_RUB_By_Payment_State", 44, 12),),
            )
        )
        hv_builders.append(
            lambda mid=mid: ensure_chart_slice(
                owner,
                "RU_HV_Bar_Revenue_RUB_By_Payment_State",
                "bar",
                mid,
                {"groupby": ["payment_state"], "metrics": ["sum__revenue_rub"], "row_limit": 100},
            )
        )
        hv_layouts.append(
            ChartLayout(
                rid("HV", "r5"),
                ((rid("HV", "c5"), "RU_HV_Pie_Revenue_RUB_By_Currency", 44, 12),),
            )
        )
        hv_builders.append(
            lambda mid=mid: ensure_chart_slice(
                owner,
                "RU_HV_Pie_Revenue_RUB_By_Currency",
                "pie",
                mid,
                {"groupby": ["currency"], "metric": "sum__revenue_rub", "row_limit": 100},
            )
        )

    if not hv_layouts:
        hv_intro = _intro_block_finance_demo(
            "Финансы (демо Postgres)",
            "<p><b>Таблицы demo_fin ещё не заполнены.</b> Запустите <code>dag_spark_hive_finance_cbr_demo</code> после marts и повторите bootstrap.</p>",
            SLUG_FINANCE_DEMO,
        )

    ensure_dashboard_with_charts(
        SLUG_FINANCE_DEMO,
        "Финансы (демо: Spark, API ЦБ, Postgres)",
        hv_intro,
        24,
        hv_layouts,
        hv_builders,
    )

    legacy = db.session.query(Slice).filter(Slice.slice_name.like("TM_%")).all()
    for sl in legacy:
        db.session.delete(sl)
    if legacy:
        db.session.commit()
        logger.info("Removed %s legacy TM_* chart slices", len(legacy))


def main() -> None:
    from flask import g
    from flask_login import login_user
    from superset import security_manager
    from superset.app import create_app

    app = create_app()
    username = os.getenv("SUPERSET_ADMIN_USERNAME", os.getenv("SUPERSET_ADMIN_USER", "admin"))
    with app.app_context():
        with app.test_request_context():
            user = security_manager.find_user(username=username)
            if not user:
                raise RuntimeError(f"FAB user not found: {username}")
            login_user(user)
            g.user = user
            _bootstrap_inner()


if __name__ == "__main__":
    main()
