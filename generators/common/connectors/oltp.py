import logging
import time
from typing import Iterable, List, Tuple

import psycopg

from factories.reference import ProductRef, SellerRef, UserRef


log = logging.getLogger("connectors.oltp")


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
                cur.execute(
                    """
                    INSERT INTO users (email, full_name)
                    VALUES (%s, %s)
                    ON CONFLICT (email) DO UPDATE SET full_name = EXCLUDED.full_name
                    RETURNING user_id;
                    """,
                    (u.email, u.full_name),
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
    ) -> int:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (user_id, status, currency_code, total_amount)
                VALUES (%s, %s, %s, %s)
                RETURNING order_id;
                """,
                (user_id, status, currency_code, total_amount),
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

    def get_table_count(self, table: str) -> int:
        conn = self._require_conn()
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            row = cur.fetchone()
            return int(row[0]) if row else 0
