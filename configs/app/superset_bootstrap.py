#!/usr/bin/env python3

from __future__ import annotations

import json
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("superset_bootstrap")

DW_SCHEMA = "dwh_marts"
DB_NAME = os.getenv("TECHMART_SUPERSET_DATABASE_LABEL", "TechMart DWH")
DASHBOARD_SLUG = "techmart-olap-overview"
TABLES = (
    "fct_daily_sales",
    "fct_orders",
    "fct_payments",
    "dim_customers",
    "dim_products",
)


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


def _bootstrap_inner() -> None:
    from superset import security_manager
    from superset.commands.dataset.create import CreateDatasetCommand
    from superset.commands.database.create import CreateDatabaseCommand
    from superset.commands.database.exceptions import DatabaseInvalidError
    from superset.commands.dataset.exceptions import DatasetInvalidError
    from superset.connectors.sqla.models import SqlaTable
    from superset.examples.helpers import get_slice_json, merge_slice, update_slice_ids
    from superset.extensions import db
    from superset.models.core import Database
    from superset.models.dashboard import Dashboard
    from superset.models.slice import Slice
    from superset.utils.core import DatasourceType

    def ensure_olap_database() -> Database:
        existing = db.session.query(Database).filter_by(database_name=DB_NAME).one_or_none()
        if existing:
            logger.info("Database %s exists id=%s", DB_NAME, existing.id)
            return existing
        try:
            db_obj = CreateDatabaseCommand(
                {
                    "database_name": DB_NAME,
                    "sqlalchemy_uri": _dwh_uri(),
                    "expose_in_sqllab": True,
                    "allow_ctas": False,
                    "allow_cvas": False,
                    "allow_dml": False,
                    "extra": "{}",
                }
            ).run()
            db.session.commit()
            logger.info("Created OLAP database entry %s", DB_NAME)
            return db_obj
        except DatabaseInvalidError:
            logger.exception("Cannot create OLAP database entry")
            raise

    def ensure_dataset(database: Database, table_name: str) -> SqlaTable | None:
        exists = (
            db.session.query(SqlaTable)
            .filter_by(
                database_id=database.id,
                schema=DW_SCHEMA,
                table_name=table_name,
            )
            .first()
        )
        if exists:
            return exists
        try:
            owner = ensure_owner()
            ds = CreateDatasetCommand(
                {
                    "database": database.id,
                    "schema": DW_SCHEMA,
                    "table_name": table_name,
                    "owners": [owner.id],
                }
            ).run()
            if table_name == "fct_daily_sales":
                ds.main_dttm_col = "order_date"
            elif table_name == "fct_orders":
                ds.main_dttm_col = "order_ts"
            elif table_name == "fct_payments":
                ds.main_dttm_col = "payment_ts"
            db.session.flush()
            ds.fetch_metadata()
            db.session.commit()
            logger.info("Registered dataset id=%s %s.%s", ds.id, DW_SCHEMA, table_name)
            return ds
        except DatasetInvalidError as ex:
            detail = [str(e) for e in getattr(ex, "_exceptions", ())] or [str(ex)]
            logger.warning(
                "Dataset %s invalid: %s",
                table_name,
                "; ".join(detail),
            )
            db.session.rollback()
            return None
        except Exception:
            logger.exception("Dataset %s not available.", table_name)
            db.session.rollback()
            return None

    def ensure_owner():
        username = os.getenv("SUPERSET_ADMIN_USERNAME", "admin")
        user = security_manager.find_user(username=username)
        if not user:
            raise RuntimeError(f"FAB user not found: {username}")
        return user

    def ensure_dashboard_bundle(ds_ids: dict[str, int]):
        if db.session.query(Dashboard).filter_by(slug=DASHBOARD_SLUG).first():
            logger.info("Dashboard %s already exists", DASHBOARD_SLUG)
            return

        dd = ds_ids["fct_daily_sales"]
        dp = ds_ids["fct_payments"]
        dc = ds_ids["dim_customers"]

        owner = ensure_owner()

        sl_sales = Slice(
            slice_name="TechMart: Gross sales (daily)",
            viz_type="echarts_timeseries_line",
            params=get_slice_json(
                {
                    "datasource": f"{dd}__table",
                    "viz_type": "echarts_timeseries_line",
                    "time_range": "No filter",
                    "row_limit": 100000,
                },
                granularity_sqla="order_date",
                metrics=["sum__gross_sales"],
            ),
            datasource_id=dd,
            datasource_type=DatasourceType.TABLE.value,
            owners=[owner],
        )

        sl_pay = Slice(
            slice_name="TechMart: Payments amount trend",
            viz_type="echarts_timeseries_line",
            params=get_slice_json(
                {
                    "datasource": f"{dp}__table",
                    "viz_type": "echarts_timeseries_line",
                    "time_range": "No filter",
                    "row_limit": 100000,
                },
                granularity_sqla="payment_ts",
                metrics=["sum__amount"],
            ),
            datasource_id=dp,
            datasource_type=DatasourceType.TABLE.value,
            owners=[owner],
        )

        sl_pie = Slice(
            slice_name="TechMart: Customer segments",
            viz_type="pie",
            params=get_slice_json(
                {
                    "datasource": f"{dc}__table",
                    "viz_type": "pie",
                    "row_limit": 500,
                },
                groupby=["customer_segment"],
                metric="count",
            ),
            datasource_id=dc,
            datasource_type=DatasourceType.TABLE.value,
            owners=[owner],
        )

        slices = [sl_sales, sl_pay, sl_pie]

        intro = (
            "<div style='padding:10px'><h2>TechMart DWH OLAP</h2>"
            "<p>Layering corresponds to docs/diagrams/data_vault_flow.md; "
            "schemas: docs/diagrams/dwh-schemas.md.</p>"
            "<p>dwh_marts materialized via dbt (project DataOps Showcase).</p></div>"
        )

        position = {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {
                "type": "GRID",
                "id": "GRID_ID",
                "children": ["ROW_MD", "ROW_S", "ROW_P", "ROW_C"],
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
                "meta": {"code": intro, "width": 12, "height": 30},
            },
            "ROW_S": {
                "type": "ROW",
                "id": "ROW_S",
                "children": ["CH_S"],
                "parents": ["ROOT_ID", "GRID_ID"],
            },
            "CH_S": {
                "type": "CHART",
                "id": "CH_S",
                "parents": ["ROOT_ID", "GRID_ID", "ROW_S"],
                "children": [],
                "meta": {
                    "chartId": 1,
                    "sliceName": "TechMart: Gross sales (daily)",
                    "uuid": "00000000-0000-4000-a000-sales",
                    "height": 50,
                    "width": 12,
                },
            },
            "ROW_P": {
                "type": "ROW",
                "id": "ROW_P",
                "children": ["CH_P"],
                "parents": ["ROOT_ID", "GRID_ID"],
            },
            "CH_P": {
                "type": "CHART",
                "id": "CH_P",
                "parents": ["ROOT_ID", "GRID_ID", "ROW_P"],
                "children": [],
                "meta": {
                    "chartId": 1,
                    "sliceName": "TechMart: Payments amount trend",
                    "uuid": "00000000-0000-4000-a000-pay",
                    "height": 50,
                    "width": 12,
                },
            },
            "ROW_C": {
                "type": "ROW",
                "id": "ROW_C",
                "children": ["CH_C"],
                "parents": ["ROOT_ID", "GRID_ID"],
            },
            "CH_C": {
                "type": "CHART",
                "id": "CH_C",
                "parents": ["ROOT_ID", "GRID_ID", "ROW_C"],
                "children": [],
                "meta": {
                    "chartId": 1,
                    "sliceName": "TechMart: Customer segments",
                    "uuid": "00000000-0000-4000-a000-seg",
                    "height": 55,
                    "width": 8,
                },
            },
        }

        for sl in slices:
            merge_slice(sl)
        db.session.commit()

        update_slice_ids(position)

        dash = Dashboard(
            dashboard_title="TechMart DWH Business Overview",
            slug=DASHBOARD_SLUG,
            published=True,
            position_json=json.dumps(position),
            owners=[owner],
        )
        dash.slices = [db.session.query(Slice).filter_by(slice_name=s.slice_name).one() for s in slices]
        db.session.add(dash)
        db.session.commit()
        logger.info("Dashboard slug=%s created", DASHBOARD_SLUG)

    need = {"fct_daily_sales", "fct_payments", "dim_customers"}

    olap = ensure_olap_database()
    reg: dict[str, int] = {}
    for t in TABLES:
        ds = ensure_dataset(olap, t)
        if ds is not None:
            reg[t] = ds.id

    missing = sorted(need - set(reg.keys()))
    if missing:
        logger.warning(
            "Skipping dashboards (datasets missing after dbt: %s).",
            missing,
        )
        return

    payload = {k: reg[k] for k in need}
    ensure_dashboard_bundle(payload)


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
