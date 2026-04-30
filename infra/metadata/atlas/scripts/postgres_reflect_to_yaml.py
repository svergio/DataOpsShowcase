#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dsn", default=os.environ.get("PG_REFLECT_DSN", ""), help="postgresql://user:pass@host:port/dbname")
    p.add_argument("--output", type=argparse.FileType("w"), default="-")
    p.add_argument(
        "--cluster",
        default=os.environ.get("ATLAS_PG_CLUSTER_NAME", "dataops"),
        help="Atlas hive_db/hive_table cluster suffix (qualifiedName @{cluster}).",
    )
    p.add_argument(
        "--network",
        default=os.environ.get("ATLAS_PG_NETWORK_TAG", "dataops_net"),
        help="Echoed only in JDBC metadata Processes (documentation).",
    )
    p.add_argument(
        "--logical-jdbc-host",
        default=os.environ.get("ATLAS_PG_JDBC_HOST", "postgres_oltp"),
        help="Host label used in legacy Process qualifiedNames for documentation.",
    )
    p.add_argument(
        "--emit-entities",
        choices=("none", "hive", "process"),
        default="none",
        help="none: inventory only; hive: hive_db + hive_table; process: one Process per table.",
    )
    args = p.parse_args()
    if not args.dsn:
        import sys

        print(
            "Provide --dsn or PG_REFLECT_DSN (e.g. postgresql://oltp_user:oltp_pass@localhost:5433/techmart_oltp).",
            file=sys.stderr,
        )
        raise SystemExit(1)
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError as exc:
        raise SystemExit("Install deps: pip install psycopg2-binary") from exc

    conn = psycopg2.connect(args.dsn)
    try:
        db_name = ""
        params = getattr(conn, "get_dsn_parameters", lambda: {})()
        if isinstance(params, dict):
            db_name = (params.get("dbname") or "").strip()
        if not db_name:
            import re

            m = re.search(r"/([^/?]+)(?:\?|$)", args.dsn)
            db_name = m.group(1) if m else "postgres"

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog','information_schema')
                  AND table_type = 'BASE TABLE'
                ORDER BY table_schema, table_name;
                """
            )
            rows = cur.fetchall()
            col_counts: dict[tuple[str, str], int] = {}
            if rows:
                cur.execute(
                    """
                    SELECT table_schema, table_name, COUNT(*)::int AS c
                    FROM information_schema.columns
                    WHERE table_schema NOT IN ('pg_catalog','information_schema')
                    GROUP BY table_schema, table_name;
                    """
                )
                for r in cur.fetchall():
                    col_counts[(r["table_schema"], r["table_name"])] = r["c"]
    finally:
        conn.close()

    try:
        import yaml
    except ImportError as exc:
        raise SystemExit("Install deps: pip install pyyaml") from exc

    note = {
        "reflection_note": "Generated for Atlas ingestion; verify cluster and JDBC labels match deployment.",
        "table_count": len(rows),
        "sample": [dict(r) for r in rows[:50]],
    }
    out_doc: dict = {"inventory": note}
    if args.emit_entities == "none":
        yaml.safe_dump(note, args.output, sort_keys=False, allow_unicode=True)
        return

    cl = args.cluster
    entities: list[dict] = []
    if args.emit_entities == "hive":
        entities.append(
            {
                "typeName": "hive_db",
                "attributes": {
                    "name": db_name,
                    "qualifiedName": f"{db_name}@{cl}",
                    "clusterName": cl,
                    "description": f"Postgres database {db_name} mirrored as hive_db for catalog (logical).",
                },
            }
        )
        for r in rows:
            sch = str(r["table_schema"])
            tbl = str(r["table_name"])
            qtbl = f"{db_name}.{sch}.{tbl}"
            qn = f"{qtbl}@{cl}"
            cc = col_counts.get((sch, tbl))
            entities.append(
                {
                    "typeName": "hive_table",
                    "relationshipAttributes": {
                        "db": {
                            "typeName": "hive_db",
                            "uniqueAttributes": {"qualifiedName": f"{db_name}@{cl}"},
                        },
                    },
                    "attributes": {
                        "name": tbl,
                        "qualifiedName": qn,
                        "description": f"Pg {sch}.{tbl}" + (f", columns≈{cc}" if cc is not None else ""),
                    },
                }
            )
    elif args.emit_entities == "process":
        for r in rows:
            sch = str(r["table_schema"])
            tbl = str(r["table_name"])
            qtbl = f"{db_name}.{sch}.{tbl}"
            cc = col_counts.get((sch, tbl))
            entities.append(
                {
                    "typeName": "Process",
                    "attributes": {
                        "name": f"pg.{qtbl}",
                        "qualifiedName": f"jdbc://{args.logical_jdbc_host}/{db_name}#{sch}.{tbl}@{args.network}",
                        "description": "INFORMATION_SCHEMA row" + (f", columns={cc}" if cc is not None else ""),
                    },
                }
            )

    out_doc = {
        **note,
        "entities": entities,
    }
    yaml.safe_dump(out_doc, args.output, sort_keys=False, allow_unicode=True)


if __name__ == "__main__":
    main()
