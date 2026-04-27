CREATE SCHEMA IF NOT EXISTS public;

CREATE TABLE IF NOT EXISTS users (
  user_id BIGSERIAL PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  full_name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sellers (
  seller_id BIGSERIAL PRIMARY KEY,
  seller_name TEXT NOT NULL,
  rating NUMERIC(3, 2),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
  product_id BIGSERIAL PRIMARY KEY,
  seller_id BIGINT NOT NULL REFERENCES sellers(seller_id),
  sku TEXT NOT NULL UNIQUE,
  product_name TEXT NOT NULL,
  category TEXT,
  price NUMERIC(12, 2) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
  order_id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(user_id),
  order_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status TEXT NOT NULL,
  currency_code CHAR(3) NOT NULL DEFAULT 'USD',
  total_amount NUMERIC(12, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
  order_item_id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL REFERENCES orders(order_id),
  product_id BIGINT NOT NULL REFERENCES products(product_id),
  quantity INT NOT NULL CHECK (quantity > 0),
  unit_price NUMERIC(12, 2) NOT NULL
);
