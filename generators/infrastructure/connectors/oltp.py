import logging
import time
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple

import psycopg
from psycopg import sql

from common.factories.reference import ProductRef, SellerRef, UserRef


log = logging.getLogger("connectors.oltp")

DEFAULT_EXT_DDL_CANONICAL = Path("/app/sql/02b_oltp_marketing_hr_finance.sql")

def _split_sql_statements(body: str) -> List[str]:
    lines_out = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        lines_out.append(line)
    blob = "\n".join(lines_out)

    stmts: List[str] = []
    buf: List[str] = []
    in_quote = False
    i = 0
    while i < len(blob):
        c = blob[i]
        if c == "'":
            if in_quote:
                if i + 1 < len(blob) and blob[i + 1] == "'":
                    buf.append("''")
                    i += 2
                    continue
                in_quote = False
                buf.append("'")
                i += 1
                continue
            in_quote = True
            buf.append("'")
            i += 1
            continue
        if c == ";" and not in_quote:
            part = "".join(buf).strip()
            if part:
                stmts.append(part + ";")
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail + (";" if not tail.endswith(";") else ""))
    return stmts


_ALLOWED_EXT_TABLES = frozenset(
    {
        "marketing_campaigns",
        "seo_keywords",
        "feature_flags",
        "employees",
        "general_ledger",
    }
)


class OltpWriter:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.conn: psycopg.Connection | None = None

    def connect(self, retries: int = 30, delay: float = 2.0) -> None:
        last_err: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                self.conn = psycopg.connect(self.dsn, autocommit=True)
                log.info("OLTP connection established (attempt %s)", attempt)
                return
            except Exception as exc:
                last_err = exc
                log.warning("OLTP connect attempt %s failed: %s", attempt, exc)
                time.sleep(delay)
        raise RuntimeError(f"Cannot connect to OLTP: {last_err}")

    def ensure_extension_tables(self, sql_path: str) -> None:
        path = Path(sql_path).expanduser()
        if not path.is_file():
            alt = DEFAULT_EXT_DDL_CANONICAL
            if alt.is_file():
                path = alt
                log.info("Using bundled OLTP extensions DDL %s", path)
            else:
                raise RuntimeError(
                    "OLTP extensions DDL missing (looked up "
                    f"{sql_path!s} and {alt}): rebuild the data-generator image "
                    "(Dockerfile must COPY services/postgres/init/02b_oltp_marketing_hr_finance.sql) "
                    "or bind-mount that file to /app/sql/02b_oltp_marketing_hr_finance.sql."
                )
        body = path.read_text(encoding="utf-8").strip()
        if not body:
            return
        conn = self._require_conn()
        stmts = _split_sql_statements(body)
        log.info(
            "Applying OLTP extension DDL from %s (%s statements)",
            sql_path,
            len(stmts),
        )
        try:
            with conn.cursor() as cur:
                for stmt in stmts:
                    cur.execute(stmt)
            log.info("OLTP extension DDL applied")
        except Exception:
            log.exception(
                "OLTP extension DDL failed (%s): ensure Postgres user can CREATE TABLE",
                sql_path,
            )
            raise

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def _require_conn(self) -> psycopg.Connection:
        if self.conn is None:
            raise RuntimeError("OLTP connection is not initialized")
        return self.conn

    def upsert_users(self, users: Iterable[UserRef]) -> List[int]:
        conn = self._require_conn()
        ids: List[int] = []
        with conn.cursor() as cur:
            for u in users:
                leg = getattr(u, "legacy_crm_customer_id", None)
                cur.execute(
                    """
                    INSERT INTO users (email, full_name, legacy_crm_customer_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (email) DO UPDATE SET
                      full_name = EXCLUDED.full_name,
                      legacy_crm_customer_id = COALESCE(
                          EXCLUDED.legacy_crm_customer_id,
                          users.legacy_crm_customer_id
                      )
                    RETURNING user_id;
                    """,
                    (u.email, u.full_name, leg),
                )
                row = cur.fetchone()
                if row is not None:
                    ids.append(int(row[0]))
        return ids

    def insert_sellers(self, sellers: Iterable[SellerRef]) -> List[int]:
        conn = self._require_conn()
        ids: List[int] = []
        with conn.cursor() as cur:
            for s in sellers:
                cur.execute(
                    """
                    INSERT INTO sellers (seller_name, rating)
                    VALUES (%s, %s)
                    RETURNING seller_id;
                    """,
                    (s.seller_name, s.rating),
                )
                row = cur.fetchone()
                if row is not None:
                    ids.append(int(row[0]))
        return ids

    def upsert_products(self, products: Iterable[ProductRef]) -> List[int]:
        conn = self._require_conn()
        ids: List[int] = []
        with conn.cursor() as cur:
            for p in products:
                cur.execute(
                    """
                    INSERT INTO products (
                        seller_id, sku, product_name, category, price, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (sku) DO UPDATE SET
                        product_name = EXCLUDED.product_name,
                        category = EXCLUDED.category,
                        price = EXCLUDED.price,
                        is_active = EXCLUDED.is_active
                    RETURNING product_id;
                    """,
                    (
                        p.seller_id,
                        p.sku,
                        p.product_name,
                        p.category,
                        p.price,
                        p.is_active,
                    ),
                )
                row = cur.fetchone()
                if row is not None:
                    ids.append(int(row[0]))
        return ids

    def insert_order(
        self,
        user_id: int,
        currency_code: str,
        total_amount: float,
        status: str,
        items: List[Tuple[int, int, float]],
        *,
        coupon_code: str | None = None,
        campaign_id: int | None = None,
        legacy_campaign_code: str | None = None,
        legacy_order_ref: str | None = None,
        subtotal_before_discount: float | None = None,
        discount_amount: float = 0.0,
        order_lineage: str = "canonical",
    ) -> int:
        conn = self._require_conn()
        sub = (
            round(float(subtotal_before_discount), 2)
            if subtotal_before_discount is not None
            else round(float(total_amount) + float(discount_amount), 2)
        )
        disc = round(float(discount_amount), 2)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (
                  user_id, status, currency_code, total_amount,
                  coupon_code, campaign_id, legacy_campaign_code,
                  legacy_order_ref, subtotal_before_discount,
                  discount_amount, order_lineage
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING order_id;
                """,
                (
                    user_id,
                    status,
                    currency_code,
                    total_amount,
                    coupon_code,
                    campaign_id,
                    legacy_campaign_code,
                    legacy_order_ref,
                    sub,
                    disc,
                    order_lineage,
                ),
            )
            order_id_row = cur.fetchone()
            if order_id_row is None:
                raise RuntimeError("Failed to insert order")
            order_id = int(order_id_row[0])
            cur.executemany(
                """
                INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                VALUES (%s, %s, %s, %s);
                """,
                [(order_id, pid, qty, price) for pid, qty, price in items],
            )
        return order_id

    def get_table_count(self, table: str) -> Optional[int]:
        if table not in _ALLOWED_EXT_TABLES:
            raise ValueError(f"unsupported table name for extension count: {table!r}")
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                  SELECT 1 FROM information_schema.tables
                  WHERE table_schema = 'public' AND table_name = %s
                );
                """,
                (table,),
            )
            row = cur.fetchone()
            if row is None or row[0] is not True:
                return None
            cur.execute(
                sql.SQL("SELECT COUNT(*) FROM {};").format(sql.Identifier(table))
            )
            cnt = cur.fetchone()
            return int(cnt[0]) if cnt else 0

    def fetch_campaign_ids(self) -> List[int]:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT campaign_id FROM marketing_campaigns ORDER BY campaign_id;"
            )
            return [int(r[0]) for r in cur.fetchall()]

    def fetch_keyword_ids(self) -> List[int]:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT keyword_id FROM seo_keywords ORDER BY keyword_id;")
            return [int(r[0]) for r in cur.fetchall()]

    def fetch_employee_ids_active(self) -> List[int]:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT employee_id FROM employees WHERE employment_status = %s ORDER BY employee_id;",
                ("ACTIVE",),
            )
            return [int(r[0]) for r in cur.fetchall()]

    def insert_marketing_campaigns(
        self,
        rows: Sequence[Tuple[Any, ...]],
    ) -> None:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO marketing_campaigns (
                  campaign_name, campaign_type, channel, budget, currency,
                  start_date, end_date, target_audience, status, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s::date, %s::date, CAST(%s AS jsonb), %s, %s);
                """,
                rows,
            )

    def insert_seo_keywords(self, rows: Sequence[Tuple[Any, ...]]) -> None:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO seo_keywords (
                  keyword, keyword_category, target_url, search_volume,
                  competition_score, cpc_estimate, currency, current_rank, target_rank
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                rows,
            )

    def insert_feature_flags(self, rows: Sequence[Tuple[Any, ...]]) -> None:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO feature_flags (
                  flag_key, flag_name, description, is_enabled, rollout_percentage, targeting_rules
                ) VALUES (%s, %s, %s, %s, %s, CAST(%s AS jsonb));
                """,
                rows,
            )

    def insert_employees(self, rows: Sequence[Tuple[Any, ...]]) -> None:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO employees (
                  employee_number, first_name, last_name, email,
                  department, job_title, level, manager_id,
                  hire_date, termination_date, employment_status,
                  location, remote_status, salary, currency
                ) VALUES (
                  %s, %s, %s, %s, %s, %s, %s, %s,
                  %s::date, %s::date, %s, %s, %s, %s, %s
                );
                """,
                rows,
            )

    def update_employee_managers(self, pairs: Sequence[Tuple[int, int]]) -> None:
        conn = self._require_conn()
        with conn.cursor() as cur:
            for eid, mid in pairs:
                cur.execute(
                    "UPDATE employees SET manager_id = %s WHERE employee_id = %s;",
                    (mid, eid),
                )

    def insert_gl_lines(self, rows: Sequence[Tuple[Any, ...]]) -> None:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO general_ledger (
                  entry_date, entry_number, account_code, account_name, account_type,
                  debit_amount, credit_amount, currency, transaction_type,
                  reference_id, reference_type, description, posted_by
                ) VALUES (
                  %s::date, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                );
                """,
                rows,
            )
