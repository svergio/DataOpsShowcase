# 📋 TechMart Data Generation Specification v1.0

**Статус**: Production-Ready  
**Версия**: 1.0.0  
**Дата**: 2025-04-27  
**Автор**: Data Engineering Team

---

## 📦 Часть 1. Архитектура и бизнес-кейс

### Бизнес-кейс: TechMart Marketplace

**Описание**: Международный marketplace электроники с multi-currency support, где:
- Продавцы из разных стран размещают товары
- Покупатели могут платить в своей валюте
- Автоматическая конвертация по курсу на момент покупки
- Поддержка возвратов, скидок, промокодов
- Tracking доставок
- Real-time события пользователей

**Географическое покрытие**:
- США (40% пользователей) - USD
- Европа (35%) - EUR, GBP
- Азия (20%) - JPY, CNY
- Другие (5%) - AUD, CAD, CHF

### High-Level Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA GENERATION LAYER                        │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   OLTP DB    │    │  MinIO/S3    │    │    Kafka     │
│  PostgreSQL  │    │   Buckets    │    │   Topics     │
│              │    │              │    │              │
│ - customers  │    │ - payments/  │    │ - events     │
│ - orders     │    │ - returns/   │    │ - payments   │
│ - products   │    │ - invoices/  │    │ - orders     │
│ - payments   │    │ - photos/    │    │ - shipments  │
│ ...          │    │ ...          │    │ ...          │
└──────────────┘    └──────────────┘    └──────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌──────────────────┐
                    │  Data Pipelines  │
                    │   (Airflow +     │
                    │    Spark + dbt)  │
                    └──────────────────┘
```

### Data Flow Patterns

1. **OLTP → Batch Ingestion**: Ежедневная экстракция в MinIO/S3
2. **MinIO → Event Processing**: File landing triggers DAG
3. **Kafka → Streaming**: Real-time consumption и aggregation
4. **Cross-source Reconciliation**: Payments в DB vs MinIO vs Kafka

---

## 📑 Часть 2. OLTP Schema (PostgreSQL)

### ERD Overview

```
customers ──┬── addresses
            │
            ├── carts ─── cart_items ─── products ─── product_categories
            │                                    │
            └── orders ──┬── order_items ────────┘
                         │
                         ├── payments ─── payment_methods
                         │                      │
                         ├── refunds ───────────┘
                         │
                         └── shipments ─── carriers

currencies ─── fx_rates

promo_codes

sellers ─── seller_products ─── products
```

### Подробные схемы таблиц

#### 1. **customers**

```sql
CREATE TABLE customers (
    customer_id         BIGSERIAL PRIMARY KEY,
    email               VARCHAR(255) UNIQUE NOT NULL,
    phone               VARCHAR(50),
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    date_of_birth       DATE,
    registration_date   TIMESTAMP NOT NULL DEFAULT NOW(),
    country_code        CHAR(2) NOT NULL,
    preferred_currency  CHAR(3) NOT NULL,
    customer_segment    VARCHAR(20) NOT NULL, -- 'VIP', 'REGULAR', 'NEW'
    is_active           BOOLEAN DEFAULT TRUE,
    last_login_at       TIMESTAMP,
    total_orders        INT DEFAULT 0,
    lifetime_value      DECIMAL(12,2) DEFAULT 0.00,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_country ON customers(country_code);
CREATE INDEX idx_customers_segment ON customers(customer_segment);
```

**Правила генерации**:
- **Объём**: 100,000 customers (стартовая база)
- **Приращение**: +500-1500 / день (новые регистрации)
- **Распределение по странам**:
  - US: 40% (country_code='US', preferred_currency='USD')
  - GB: 15% (GB/GBP)
  - DE: 10% (DE/EUR)
  - FR: 8% (FR/EUR)
  - JP: 12% (JP/JPY)
  - CN: 10% (CN/CNY)
  - Others: 5% (AU, CA, CH)
  
- **Сегменты**:
  - VIP: 5% (total_orders >= 20, lifetime_value >= $10k)
  - REGULAR: 60% (total_orders >= 3)
  - NEW: 35% (total_orders < 3)
  
- **Email**: `{first_name}.{last_name}{random_num}@{domain}` (gmail.com 40%, yahoo.com 20%, custom 40%)
- **Age distribution**: Normal(μ=35, σ=12), range [18-80]
- **last_login_at**: Exponential decay (чаще недавние логины), 15% NULL (churned users)

**Edge cases**:
- 2% emails с unicode символами
- 1% без phone
- 0.5% duplicate emails (для тестирования constraints)
- 5% is_active=FALSE

---

#### 2. **addresses**

```sql
CREATE TABLE addresses (
    address_id      BIGSERIAL PRIMARY KEY,
    customer_id     BIGINT NOT NULL REFERENCES customers(customer_id),
    address_type    VARCHAR(20) NOT NULL, -- 'BILLING', 'SHIPPING'
    street_line1    VARCHAR(255) NOT NULL,
    street_line2    VARCHAR(255),
    city            VARCHAR(100) NOT NULL,
    state_province  VARCHAR(100),
    postal_code     VARCHAR(20) NOT NULL,
    country_code    CHAR(2) NOT NULL,
    is_default      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_addresses_customer ON addresses(customer_id);
CREATE INDEX idx_addresses_country ON addresses(country_code);
```

**Правила генерации**:
- **Объём**: 150,000 addresses (1.5 avg per customer)
- **Распределение**: 
  - 70% customers: 1 address (both billing & shipping)
  - 20%: 2 addresses (separate billing/shipping)
  - 8%: 3+ addresses (multiple shipping)
  - 2%: 0 addresses (edge case)
  
- **Валидация**: postal_code format по стране (US: 5 digits, GB: alphanumeric)
- **is_default**: ровно 1 на customer+address_type (enforce в генераторе)

**Edge cases**:
- 1% с очень длинными street_line1 (>200 chars)
- 3% без state_province (страны где не требуется)
- 0.5% invalid postal_code format

---

#### 3. **product_categories**

```sql
CREATE TABLE product_categories (
    category_id     SERIAL PRIMARY KEY,
    category_name   VARCHAR(100) UNIQUE NOT NULL,
    parent_category_id INT REFERENCES product_categories(category_id),
    level           INT NOT NULL, -- 1=root, 2=subcategory, 3=leaf
    created_at      TIMESTAMP DEFAULT NOW()
);
```

**Правила генерации**:
- **Объём**: 50 categories (статичный справочник)
- **Структура**: 3-level hierarchy
  - Level 1 (root): 5 categories (Electronics, Computers, Mobile, Audio, Gaming)
  - Level 2: 15 categories (Laptops, Tablets, Smartphones, Headphones, etc.)
  - Level 3: 30 categories (Gaming Laptops, Ultrabooks, Wireless Earbuds, etc.)

**Фиксированный список**:
```
1. Electronics
  ├── 2. Computers
  │   ├── 6. Laptops
  │   ├── 7. Desktops
  │   └── 8. Tablets
  ├── 3. Mobile Devices
  │   ├── 9. Smartphones
  │   └── 10. Smartwatches
  ...
```

---

#### 4. **sellers**

```sql
CREATE TABLE sellers (
    seller_id       SERIAL PRIMARY KEY,
    seller_name     VARCHAR(200) NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    country_code    CHAR(2) NOT NULL,
    rating          DECIMAL(3,2), -- 0.00 - 5.00
    total_sales     BIGINT DEFAULT 0,
    is_verified     BOOLEAN DEFAULT FALSE,
    joined_date     DATE NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

**Правила генерации**:
- **Объём**: 500 sellers (статичный)
- **Распределение по странам**: 
  - US: 30%, CN: 25%, DE: 15%, JP: 10%, Others: 20%
- **rating**: Beta distribution (α=20, β=4) → skewed к 4.0-5.0
- **is_verified**: 80% TRUE
- **joined_date**: Uniform[2020-01-01, 2024-12-31]

---

#### 5. **products**

```sql
CREATE TABLE products (
    product_id          BIGSERIAL PRIMARY KEY,
    seller_id           INT NOT NULL REFERENCES sellers(seller_id),
    category_id         INT NOT NULL REFERENCES product_categories(category_id),
    product_name        VARCHAR(300) NOT NULL,
    brand               VARCHAR(100),
    model               VARCHAR(100),
    description         TEXT,
    base_price          DECIMAL(10,2) NOT NULL,
    currency            CHAR(3) NOT NULL,
    stock_quantity      INT NOT NULL DEFAULT 0,
    weight_kg           DECIMAL(8,3),
    dimensions_cm       VARCHAR(50), -- "30x20x5"
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_seller ON products(seller_id);
CREATE INDEX idx_products_active ON products(is_active);
```

**Правила генерации**:
- **Объём**: 10,000 products
- **Приращение**: +20-50 / день (новые товары)
  
**Ценовые диапазоны по категориям**:
```python
{
    'Smartphones': (200, 1500),
    'Laptops': (400, 3500),
    'Headphones': (20, 600),
    'Tablets': (150, 1200),
    'Smartwatches': (100, 800),
    # ...
}
```

- **currency**: Matching seller's country (US sellers → USD, DE → EUR)
- **stock_quantity**: Log-normal(μ=3, σ=1.5), range [0-1000]
  - 10% out of stock (=0)
  - 60% low stock (1-20)
  - 30% in stock (21-1000)
  
- **brand**: Top 20 brands (Apple 15%, Samsung 12%, Sony 8%, ...)
- **is_active**: 95% TRUE (5% discontinued)

**Edge cases**:
- 5% products без brand
- 2% с base_price < 10 (clearance)
- 1% с очень большим stock (>500)

---

#### 6. **carts**

```sql
CREATE TABLE carts (
    cart_id         BIGSERIAL PRIMARY KEY,
    customer_id     BIGINT NOT NULL REFERENCES customers(customer_id),
    status          VARCHAR(20) NOT NULL, -- 'ACTIVE', 'ABANDONED', 'CONVERTED'
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    abandoned_at    TIMESTAMP,
    converted_to_order_id BIGINT
);

CREATE INDEX idx_carts_customer ON carts(customer_id);
CREATE INDEX idx_carts_status ON carts(status);
```

**Правила генерации**:
- **Объём**: 200,000 carts (исторические)
- **Приращение**: +2000-5000 / день
  
**Распределение статусов**:
- ACTIVE: 15% (текущие корзины)
- ABANDONED: 60% (классическая e-commerce метрика)
- CONVERTED: 25% (стали orders)

- **abandoned_at**: created_at + Exponential(λ=2 days)
- **Conversion time**: created_at → converted (Median=2 hours, 95th percentile=48 hours)

---

#### 7. **cart_items**

```sql
CREATE TABLE cart_items (
    cart_item_id    BIGSERIAL PRIMARY KEY,
    cart_id         BIGINT NOT NULL REFERENCES carts(cart_id),
    product_id      BIGINT NOT NULL REFERENCES products(product_id),
    quantity        INT NOT NULL CHECK (quantity > 0),
    unit_price      DECIMAL(10,2) NOT NULL,
    currency        CHAR(3) NOT NULL,
    added_at        TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cart_items_cart ON cart_items(cart_id);
CREATE INDEX idx_cart_items_product ON cart_items(product_id);
```

**Правила генерации**:
- **Items per cart**: Poisson(λ=2.5), range [1-15]
- **quantity**: 
  - 80%: 1 item
  - 15%: 2-3 items
  - 5%: 4-10 items
  
- **unit_price**: Берется из products.base_price на момент added_at (может отличаться из-за price changes)
- **currency**: Конвертируется в customer's preferred_currency через fx_rates

---

#### 8. **orders**

```sql
CREATE TABLE orders (
    order_id            BIGSERIAL PRIMARY KEY,
    customer_id         BIGINT NOT NULL REFERENCES customers(customer_id),
    billing_address_id  BIGINT REFERENCES addresses(address_id),
    shipping_address_id BIGINT REFERENCES addresses(address_id),
    order_number        VARCHAR(50) UNIQUE NOT NULL, -- "ORD-2024-001234"
    order_status        VARCHAR(30) NOT NULL,
    -- 'PENDING', 'CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'REFUNDED'
    
    subtotal            DECIMAL(12,2) NOT NULL,
    discount_amount     DECIMAL(10,2) DEFAULT 0.00,
    tax_amount          DECIMAL(10,2) NOT NULL,
    shipping_fee        DECIMAL(10,2) NOT NULL,
    total_amount        DECIMAL(12,2) NOT NULL,
    currency            CHAR(3) NOT NULL,
    
    promo_code          VARCHAR(50),
    
    ordered_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    confirmed_at        TIMESTAMP,
    shipped_at          TIMESTAMP,
    delivered_at        TIMESTAMP,
    cancelled_at        TIMESTAMP,
    
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(order_status);
CREATE INDEX idx_orders_ordered_at ON orders(ordered_at);
CREATE INDEX idx_orders_number ON orders(order_number);
```

**Правила генерации**:
- **Объём**: 500,000 orders (исторические за 12 месяцев)
- **Приращение**: +1500-3000 / день (рост 5% месяц к месяцу)
  
**Сезонность**:
- Black Friday (Nov): 3x normal
- Christmas (Dec): 2.5x
- Back to School (Aug-Sep): 1.5x
- Summer slump (Jun-Jul): 0.7x

**Распределение статусов** (на текущий момент):
- PENDING: 5%
- CONFIRMED: 8%
- PROCESSING: 12%
- SHIPPED: 15%
- DELIVERED: 55%
- CANCELLED: 3%
- REFUNDED: 2%

**Бизнес-логика**:
```python
# Timing rules (median times)
confirmed_at = ordered_at + timedelta(minutes=randint(5, 120))
shipped_at = confirmed_at + timedelta(days=choice([1,2,3,4])) # if status >= SHIPPED
delivered_at = shipped_at + timedelta(days=randint(2, 10))    # if DELIVERED

# Cancellations: 3% within first 24 hours
if random() < 0.03:
    cancelled_at = ordered_at + timedelta(hours=randint(1, 24))
```

**Ценообразование**:
```python
subtotal = sum(order_items.unit_price * quantity)
discount_amount = subtotal * promo_discount_rate  # if promo_code applied
tax_amount = (subtotal - discount_amount) * tax_rate  # country-specific
shipping_fee = calculate_shipping(weight, country)  # 5-50 USD
total_amount = subtotal - discount_amount + tax_amount + shipping_fee
```

**Tax rates по странам**:
- US: 0-10% (varies by state)
- GB: 20% VAT
- DE: 19% VAT
- JP: 10%
- CN: 13%

**order_number format**: `ORD-{YYYY}-{sequential_6_digit}`

---

#### 9. **order_items**

```sql
CREATE TABLE order_items (
    order_item_id   BIGSERIAL PRIMARY KEY,
    order_id        BIGINT NOT NULL REFERENCES orders(order_id),
    product_id      BIGINT NOT NULL REFERENCES products(product_id),
    quantity        INT NOT NULL CHECK (quantity > 0),
    unit_price      DECIMAL(10,2) NOT NULL,
    discount        DECIMAL(10,2) DEFAULT 0.00,
    subtotal        DECIMAL(10,2) NOT NULL,
    currency        CHAR(3) NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);
```

**Правила генерации**:
- **Items per order**: Poisson(λ=3), range [1-20]
- **quantity**: Same as cart_items distribution
- **unit_price**: Product price конвертируется в order.currency через fx_rates на дату ordered_at
- **discount**: Item-level скидки (bundle deals), 0% для 90%, 5-20% для 10%
- **subtotal**: unit_price * quantity - discount

---

#### 10. **payment_methods**

```sql
CREATE TABLE payment_methods (
    payment_method_id   SERIAL PRIMARY KEY,
    method_name         VARCHAR(50) UNIQUE NOT NULL,
    -- 'CREDIT_CARD', 'DEBIT_CARD', 'PAYPAL', 'STRIPE', 'BANK_TRANSFER', 'CRYPTO'
    is_active           BOOLEAN DEFAULT TRUE
);
```

**Статичный справочник**:
```sql
INSERT INTO payment_methods (payment_method_id, method_name) VALUES
(1, 'CREDIT_CARD'),
(2, 'DEBIT_CARD'),
(3, 'PAYPAL'),
(4, 'STRIPE'),
(5, 'BANK_TRANSFER'),
(6, 'CRYPTO');
```

---

#### 11. **payments**

```sql
CREATE TABLE payments (
    payment_id          BIGSERIAL PRIMARY KEY,
    order_id            BIGINT NOT NULL REFERENCES orders(order_id),
    payment_method_id   INT NOT NULL REFERENCES payment_methods(payment_method_id),
    amount              DECIMAL(12,2) NOT NULL,
    currency            CHAR(3) NOT NULL,
    payment_status      VARCHAR(20) NOT NULL,
    -- 'INITIATED', 'AUTHORIZED', 'CAPTURED', 'DECLINED', 'REFUNDED', 'FAILED'
    
    transaction_id      VARCHAR(100) UNIQUE,
    gateway_response    JSONB,
    
    initiated_at        TIMESTAMP NOT NULL,
    authorized_at       TIMESTAMP,
    captured_at         TIMESTAMP,
    failed_at           TIMESTAMP,
    
    decline_reason      VARCHAR(255),
    
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_payments_order ON payments(order_id);
CREATE INDEX idx_payments_status ON payments(payment_status);
CREATE INDEX idx_payments_transaction ON payments(transaction_id);
```

**Правила генерации**:
- **Объём**: 1:1 with orders (каждый order имеет payment attempt)
- **Дополнительно**: +3% failed payments (retries)
  
**Распределение payment_methods**:
- CREDIT_CARD: 45%
- DEBIT_CARD: 25%
- PAYPAL: 20%
- STRIPE: 8%
- BANK_TRANSFER: 1.5%
- CRYPTO: 0.5%

**Распределение статусов**:
- CAPTURED: 92%
- DECLINED: 5%
- FAILED: 2%
- REFUNDED: 1%

**Decline reasons** (для DECLINED):
```python
decline_reasons = [
    'INSUFFICIENT_FUNDS',      # 40%
    'CARD_EXPIRED',            # 20%
    'FRAUD_SUSPECTED',         # 15%
    'INVALID_CVV',             # 10%
    'CARD_BLOCKED',            # 10%
    'NETWORK_ERROR'            # 5%
]
```

**transaction_id format**: `TXN-{payment_method}-{timestamp}-{random_hash}`

**gateway_response example**:
```json
{
  "gateway": "stripe",
  "charge_id": "ch_3NXqP...",
  "network_status": "approved",
  "avs_result": "Y",
  "cvv_result": "M",
  "risk_score": 12
}
```

**Timing**:
```python
initiated_at = order.ordered_at + timedelta(seconds=randint(10, 300))
if status == 'CAPTURED':
    authorized_at = initiated_at + timedelta(seconds=randint(1, 30))
    captured_at = authorized_at + timedelta(seconds=randint(1, 60))
elif status == 'DECLINED':
    failed_at = initiated_at + timedelta(seconds=randint(5, 60))
```

---

#### 12. **refunds**

```sql
CREATE TABLE refunds (
    refund_id       BIGSERIAL PRIMARY KEY,
    payment_id      BIGINT NOT NULL REFERENCES payments(payment_id),
    order_id        BIGINT NOT NULL REFERENCES orders(order_id),
    refund_amount   DECIMAL(12,2) NOT NULL,
    currency        CHAR(3) NOT NULL,
    refund_status   VARCHAR(20) NOT NULL, -- 'PENDING', 'APPROVED', 'COMPLETED', 'REJECTED'
    refund_reason   VARCHAR(255),
    requested_at    TIMESTAMP NOT NULL,
    approved_at     TIMESTAMP,
    completed_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_refunds_payment ON refunds(payment_id);
CREATE INDEX idx_refunds_order ON refunds(order_id);
```

**Правила генерации**:
- **Объём**: 2% от orders
- **Распределение**:
  - Full refund: 70% (refund_amount = order.total_amount)
  - Partial refund: 30% (50-90% of total)
  
**Reasons**:
```python
refund_reasons = [
    'DEFECTIVE_PRODUCT',       # 30%
    'WRONG_ITEM',              # 20%
    'NOT_AS_DESCRIBED',        # 15%
    'DAMAGED_IN_SHIPPING',     # 15%
    'CHANGED_MIND',            # 10%
    'DUPLICATE_ORDER',         # 5%
    'OTHER'                    # 5%
]
```

**Status flow**:
```python
requested_at = order.delivered_at + timedelta(days=randint(1, 14))
approved_at = requested_at + timedelta(hours=randint(2, 48))  # 95% approved
completed_at = approved_at + timedelta(days=randint(3, 7))
```

---

#### 13. **carriers**

```sql
CREATE TABLE carriers (
    carrier_id      SERIAL PRIMARY KEY,
    carrier_name    VARCHAR(100) UNIQUE NOT NULL,
    country_code    CHAR(2),
    is_active       BOOLEAN DEFAULT TRUE
);
```

**Статичный справочник**:
```sql
INSERT INTO carriers (carrier_name, country_code) VALUES
('FedEx', 'US'),
('UPS', 'US'),
('DHL', NULL),  -- international
('USPS', 'US'),
('Royal Mail', 'GB'),
('Deutsche Post', 'DE'),
('Japan Post', 'JP'),
('SF Express', 'CN');
```

---

#### 14. **shipments**

```sql
CREATE TABLE shipments (
    shipment_id         BIGSERIAL PRIMARY KEY,
    order_id            BIGINT NOT NULL REFERENCES orders(order_id),
    carrier_id          INT NOT NULL REFERENCES carriers(carrier_id),
    tracking_number     VARCHAR(100) UNIQUE NOT NULL,
    shipment_status     VARCHAR(30) NOT NULL,
    -- 'LABEL_CREATED', 'PICKED_UP', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'DELIVERED', 'EXCEPTION'
    
    shipped_at          TIMESTAMP,
    estimated_delivery  DATE,
    actual_delivery     TIMESTAMP,
    
    weight_kg           DECIMAL(8,3),
    shipping_cost       DECIMAL(10,2),
    currency            CHAR(3),
    
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_shipments_order ON shipments(order_id);
CREATE INDEX idx_shipments_tracking ON shipments(tracking_number);
CREATE INDEX idx_shipments_status ON shipments(shipment_status);
```

**Правила генерации**:
- **Объём**: 1:1 с orders где status >= 'SHIPPED'
  
**Carrier selection по country**:
```python
carrier_mapping = {
    'US': ['FedEx', 'UPS', 'USPS'],  # weighted [40, 40, 20]
    'GB': ['Royal Mail', 'DHL'],     # [60, 40]
    'DE': ['Deutsche Post', 'DHL'],  # [70, 30]
    'JP': ['Japan Post', 'DHL'],     # [80, 20]
    'CN': ['SF Express', 'DHL'],     # [60, 40]
    'OTHER': ['DHL']
}
```

**tracking_number format**: `{carrier_code}{14_digits}`

**Status progression**:
```python
LABEL_CREATED → PICKED_UP (1-2 days) → IN_TRANSIT (2-5 days) → 
OUT_FOR_DELIVERY (same day) → DELIVERED
```

- **EXCEPTION**: 2% of shipments (delayed, damaged, lost)
- **estimated_delivery**: shipped_at + carrier_transit_time ± 1 day
- **actual_delivery**: 
  - 85%: on time (±1 day from estimate)
  - 10%: late (1-5 days)
  - 3%: early (1 day)
  - 2%: exception (never delivered или re-scheduled)

**shipping_cost**: Зависит от weight и distance
```python
def calculate_shipping(weight_kg, domestic=True):
    base = 5.00
    weight_cost = weight_kg * 2.50
    intl_surcharge = 0 if domestic else 15.00
    return base + weight_cost + intl_surcharge
```

---

#### 15. **currencies**

```sql
CREATE TABLE currencies (
    currency_code   CHAR(3) PRIMARY KEY,
    currency_name   VARCHAR(50) NOT NULL,
    symbol          VARCHAR(5),
    is_active       BOOLEAN DEFAULT TRUE
);
```

**Статичный справочник**:
```sql
INSERT INTO currencies VALUES
('USD', 'US Dollar', '$', TRUE),
('EUR', 'Euro', '€', TRUE),
('GBP', 'British Pound', '£', TRUE),
('JPY', 'Japanese Yen', '¥', TRUE),
('CNY', 'Chinese Yuan', '¥', TRUE),
('AUD', 'Australian Dollar', 'A$', TRUE),
('CAD', 'Canadian Dollar', 'C$', TRUE),
('CHF', 'Swiss Franc', 'CHF', TRUE);
```

---

#### 16. **fx_rates**

```sql
CREATE TABLE fx_rates (
    fx_rate_id      BIGSERIAL PRIMARY KEY,
    from_currency   CHAR(3) NOT NULL REFERENCES currencies(currency_code),
    to_currency     CHAR(3) NOT NULL REFERENCES currencies(currency_code),
    rate_date       DATE NOT NULL,
    exchange_rate   DECIMAL(15,6) NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(from_currency, to_currency, rate_date)
);

CREATE INDEX idx_fx_rates_date ON fx_rates(rate_date);
CREATE INDEX idx_fx_rates_currencies ON fx_rates(from_currency, to_currency);
```

**Правила генерации**:
- **Объём**: Ежедневные курсы для всех пар
- **Период**: Last 365 days + forward 30 days
- **Пары**: 8 currencies → 8*7 = 56 pairs per day (исключая self)
  
**Базовые курсы (на 2025-01-01)**:
```python
base_rates = {
    ('USD', 'EUR'): 0.92,
    ('USD', 'GBP'): 0.79,
    ('USD', 'JPY'): 145.50,
    ('USD', 'CNY'): 7.25,
    ('USD', 'AUD'): 1.52,
    ('USD', 'CAD'): 1.35,
    ('USD', 'CHF'): 0.88,
}
```

**Динамика** (Geometric Brownian Motion):
```python
def generate_fx_rate(base_rate, days_from_base, volatility=0.01):
    """
    S(t) = S(0) * exp((μ - σ²/2) * t + σ * W(t))
    μ = drift (0 for FX)
    σ = volatility (1% daily)
    W(t) = Wiener process
    """
    drift = 0.0
    random_shock = np.random.normal(0, volatility * np.sqrt(days_from_base))
    rate = base_rate * np.exp((drift - volatility**2 / 2) * days_from_base + random_shock)
    return round(rate, 6)
```

**Корреляции**:
- EUR/GBP: высокая корреляция (0.8)
- JPY/CNY: средняя (0.4)
- Все vs USD: inverse correlation

**Edge cases**:
- 0.1% missing dates (holidays, system downtime)
- 0.01% extreme rates (flash crash simulation)

---

#### 17. **promo_codes**

```sql
CREATE TABLE promo_codes (
    promo_code_id   SERIAL PRIMARY KEY,
    code            VARCHAR(50) UNIQUE NOT NULL,
    discount_type   VARCHAR(20) NOT NULL, -- 'PERCENTAGE', 'FIXED_AMOUNT'
    discount_value  DECIMAL(10,2) NOT NULL,
    currency        CHAR(3), -- NULL for percentage
    min_order_value DECIMAL(10,2),
    max_uses        INT,
    current_uses    INT DEFAULT 0,
    valid_from      DATE NOT NULL,
    valid_until     DATE NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_promo_codes_code ON promo_codes(code);
CREATE INDEX idx_promo_codes_active ON promo_codes(is_active);
```

**Правила генерации**:
- **Объём**: 100 active promo codes
  
**Типы**:
- PERCENTAGE: 70% (values: 5%, 10%, 15%, 20%, 25%)
- FIXED_AMOUNT: 30% (values: $10, $20, $50, $100)

**code format**: 
- `SAVE{percentage}` (e.g., SAVE20)
- `{SEASONAL}{YEAR}` (e.g., BLACKFRIDAY2024)
- `WELCOME{NUM}` (e.g., WELCOME10)

**Constraints**:
- min_order_value: 0 for small discounts, $100+ for big ones
- max_uses: 100-10000 (NULL = unlimited)
- valid_until - valid_from: 7-90 days

**Application rate**: 25% orders use promo code

---

## 📂 Часть 4. MinIO/S3 Data Generators

### Bucket Structure

```
techmart-data/
├── raw/
│   ├── payments/
│   │   └── YYYY/MM/DD/
│   │       └── payments_YYYYMMDD_HHMMSS.parquet
│   ├── returns/
│   │   └── YYYY/MM/DD/
│   │       └── returns_YYYYMMDD_{batch_id}.csv
│   ├── invoices/
│   │   └── YYYY/MM/
│   │       └── invoice_{order_number}.pdf
│   ├── product_catalog/
│   │   └── catalog_update_YYYYMMDD.csv
│   └── tax_reports/
│       └── YYYY/MM/
│           └── tax_report_{country}_YYYYMM.xml
├── staging/
└── processed/
```

---

### A) Payment Files (Parquet)

**Path**: `s3://techmart-data/raw/payments/{YYYY}/{MM}/{DD}/payments_{YYYYMMDD}_{HHMMSS}.parquet`

**Schema**:
```python
{
    "payment_id": "bigint",
    "order_id": "bigint",
    "transaction_id": "string",
    "payment_method": "string",
    "amount": "decimal(12,2)",
    "currency": "string",
    "status": "string",
    "gateway": "string",
    "card_last4": "string",  # if card
    "card_brand": "string",  # VISA, MASTERCARD, AMEX
    "authorization_code": "string",
    "decline_code": "string",  # if declined
    "risk_score": "int",
    "ip_address": "string",
    "user_agent": "string",
    "timestamp": "timestamp",
    "metadata": "json"
}
```

**Генерация**:
- **Frequency**: Every hour
- **Records per file**: ~5000-15000 (1 hour of payments)
- **File size**: 2-8 MB
- **Retention**: 90 days в raw, потом архив

**Data quality issues** (intentional):
- 0.5%: NULL transaction_id
- 1%: invalid currency code (e.g., "XXX")
- 0.2%: negative amount
- 2%: duplicate payment_id (simulating retries)
- 0.1%: malformed JSON in metadata

**Example record**:
```json
{
    "payment_id": 1234567,
    "order_id": 987654,
    "transaction_id": "TXN-STRIPE-20250427120534-a7b3c9",
    "payment_method": "CREDIT_CARD",
    "amount": 459.99,
    "currency": "USD",
    "status": "CAPTURED",
    "gateway": "stripe",
    "card_last4": "4242",
    "card_brand": "VISA",
    "authorization_code": "AUTH-739201",
    "decline_code": null,
    "risk_score": 8,
    "ip_address": "203.0.113.45",
    "user_agent": "Mozilla/5.0...",
    "timestamp": "2025-04-27T12:05:34.123Z",
    "metadata": {
        "device_fingerprint": "df_abc123",
        "3ds_enrolled": true,
        "billing_zip": "94103"
    }
}
```

---

### B) Returns Files (CSV)

**Path**: `s3://techmart-data/raw/returns/{YYYY}/{MM}/{DD}/returns_{YYYYMMDD}_{batch_id}.csv`

**Schema**:
```csv
return_id,order_id,order_item_id,product_id,return_reason,quantity,refund_amount,currency,status,requested_at,approved_at,notes
```

**Генерация**:
- **Frequency**: 3-5 files per day
- **Records per file**: 200-800
- **File size**: 50-200 KB

**Data quality issues**:
- 5%: Missing columns (truncated rows)
- 3%: Wrong delimiter (tab instead of comma in some rows)
- 2%: Duplicate headers mid-file
- 1%: Invalid date formats ("2025/04/27" vs "2025-04-27")
- 0.5%: Non-UTF8 characters in notes

**Example**:
```csv
return_id,order_id,order_item_id,product_id,return_reason,quantity,refund_amount,currency,status,requested_at,approved_at,notes
10001,987654,1,5432,DEFECTIVE_PRODUCT,1,459.99,USD,APPROVED,2025-04-20 10:30:00,2025-04-21 14:22:00,"Screen has dead pixels"
10002,987655,2,5433,WRONG_ITEM	1	89.99	EUR	PENDING	2025-04-20 11:45:00		"Ordered blue, received red"
```

---

### C) Product Catalog Updates (CSV)

**Path**: `s3://techmart-data/raw/product_catalog/catalog_update_{YYYYMMDD}.csv`

**Schema**:
```csv
product_id,seller_id,product_name,brand,category,price,currency,stock,is_active,updated_at
```

**Генерация**:
- **Frequency**: Daily at 02:00 UTC
- **Records**: 500-2000 (products with changes)
- **Change types**:
  - Price change: 60%
  - Stock update: 30%
  - Status change: 8%
  - New product: 2%

**Intentional errors**:
- 3%: Price = 0 or negative
- 2%: Stock = -5 (oversold scenario)
- 1%: Duplicate product_id (version conflict)

---

### D) Invoice PDFs

**Path**: `s3://techmart-data/raw/invoices/{YYYY}/{MM}/invoice_{order_number}.pdf`

**Генерация**:
- **Frequency**: Generated for each order (status=DELIVERED)
- **Naming**: `invoice_ORD-2025-001234.pdf`
- **Size**: 50-150 KB per PDF

**Metadata** (stored separately in `invoice_metadata.json`):
```json
{
    "order_number": "ORD-2025-001234",
    "invoice_date": "2025-04-27",
    "s3_path": "s3://techmart-data/raw/invoices/2025/04/invoice_ORD-2025-001234.pdf",
    "file_size_bytes": 87423,
    "checksum_md5": "5d41402abc4b2a76b9719d911017c592",
    "generated_at": "2025-04-27T15:30:00Z"
}
```

---

### E) Tax Reports (XML)

**Path**: `s3://techmart-data/raw/tax_reports/{YYYY}/{MM}/tax_report_{country}_{YYYYMM}.xml`

**Schema** (XML structure):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<TaxReport>
    <ReportPeriod>2025-04</ReportPeriod>
    <Country>US</Country>
    <TotalSales currency="USD">1245678.90</TotalSales>
    <TotalTax currency="USD">98765.43</TotalTax>
    <TransactionCount>15234</TransactionCount>
    <Transactions>
        <Transaction>
            <OrderID>987654</OrderID>
            <OrderDate>2025-04-15</OrderDate>
            <NetAmount>429.99</NetAmount>
            <TaxAmount>30.10</TaxAmount>
            <TaxRate>0.07</TaxRate>
        </Transaction>
        ...
    </Transactions>
</TaxReport>
```

**Генерация**:
- **Frequency**: Monthly (1st day of next month)
- **Countries**: US, GB, DE, FR, JP, CN
- **File size**: 1-10 MB (depending on transaction count)

---

## 🛰️ Часть 5. Kafka Stream Generators

### Kafka Setup

**Topics**:
```
techmart.events.clickstream      (partitions: 12, retention: 7 days)
techmart.events.orders            (partitions: 8, retention: 30 days)
techmart.payments.transactions    (partitions: 6, retention: 30 days)
techmart.shipments.tracking       (partitions: 4, retention: 30 days)
```

---

### 1) Clickstream Events

**Topic**: `techmart.events.clickstream`

**Event Types**:
- PAGE_VIEW
- PRODUCT_VIEW
- ADD_TO_CART
- REMOVE_FROM_CART
- CHECKOUT_START
- SEARCH
- FILTER_APPLIED

**Schema** (Avro):
```json
{
  "type": "record",
  "name": "ClickstreamEvent",
  "namespace": "com.techmart.events",
  "fields": [
    {"name": "event_id", "type": "string"},
    {"name": "event_type", "type": "string"},
    {"name": "timestamp", "type": "long", "logicalType": "timestamp-millis"},
    {"name": "session_id", "type": "string"},
    {"name": "customer_id", "type": ["null", "long"], "default": null},
    {"name": "product_id", "type": ["null", "long"], "default": null},
    {"name": "category_id", "type": ["null", "int"], "default": null},
    {"name": "page_url", "type": "string"},
    {"name": "referrer", "type": ["null", "string"], "default": null},
    {"name": "device_type", "type": "string"},
    {"name": "os", "type": "string"},
    {"name": "browser", "type": "string"},
    {"name": "ip_address", "type": "string"},
    {"name": "country_code", "type": "string"},
    {"name": "metadata", "type": {
      "type": "map",
      "values": "string"
    }}
  ]
}
```

**Генерация**:
- **Throughput**: 500-2000 events/second (peak hours)
- **Daily volume**: ~50M events
- **Peak times**: 
  - 10-11 AM local time: 1.5x
  - 7-9 PM local time: 2x
  - Midnight-6 AM: 0.3x

**Event flow** (user session simulation):
```python
# Typical session
1. PAGE_VIEW (homepage)
2. SEARCH ("wireless headphones")
3. PRODUCT_VIEW (product_id=5432)
4. ADD_TO_CART
5. PAGE_VIEW (cart)
6. CHECKOUT_START
# 60% abandon here
# 40% continue to order
```

**Key distribution**:
- Partition by: `hash(session_id) % 12`
- Ensures session events на одной partition для ordering

**Example event**:
```json
{
  "event_id": "evt_3NXqP2L...",
  "event_type": "PRODUCT_VIEW",
  "timestamp": 1714228800123,
  "session_id": "sess_abc123def456",
  "customer_id": 42387,
  "product_id": 5432,
  "category_id": 9,
  "page_url": "/products/wireless-headphones-pro",
  "referrer": "https://google.com/search?q=headphones",
  "device_type": "MOBILE",
  "os": "iOS",
  "browser": "Safari",
  "ip_address": "203.0.113.45",
  "country_code": "US",
  "metadata": {
    "viewport_width": "375",
    "viewport_height": "812",
    "screen_resolution": "1125x2436"
  }
}
```

**Error injection**:
- 0.5%: Malformed JSON
- 1%: Missing required fields
- 0.2%: Future timestamps (clock skew)
- 2%: Duplicate event_id

---

### 2) Order Events

**Topic**: `techmart.events.orders`

**Event Types**:
- ORDER_CREATED
- ORDER_CONFIRMED
- ORDER_CANCELLED
- ORDER_SHIPPED
- ORDER_DELIVERED

**Schema** (JSON):
```json
{
  "event_id": "string",
  "event_type": "string",
  "order_id": "integer",
  "order_number": "string",
  "customer_id": "integer",
  "timestamp": "string (ISO8601)",
  "previous_status": "string",
  "new_status": "string",
  "total_amount": "number",
  "currency": "string",
  "items_count": "integer",
  "metadata": {
    "source": "string",
    "triggered_by": "string"
  }
}
```

**Генерация**:
- **Throughput**: 20-100 events/second
- **Event ordering**: Must preserve order status transitions
- **Partition key**: `order_id % 8`

**State machine validation**:
```
CREATED → CONFIRMED → SHIPPED → DELIVERED
            ↓
        CANCELLED
```

**Example**:
```json
{
  "event_id": "ord_evt_20250427_001234",
  "event_type": "ORDER_CONFIRMED",
  "order_id": 987654,
  "order_number": "ORD-2025-001234",
  "customer_id": 42387,
  "timestamp": "2025-04-27T12:15:30.456Z",
  "previous_status": "PENDING",
  "new_status": "CONFIRMED",
  "total_amount": 459.99,
  "currency": "USD",
  "items_count": 3,
  "metadata": {
    "source": "order_service",
    "triggered_by": "payment_success"
  }
}
```

---

### 3) Payment Stream

**Topic**: `techmart.payments.transactions`

**Event Types**:
- PAYMENT_INITIATED
- PAYMENT_AUTHORIZED
- PAYMENT_CAPTURED
- PAYMENT_DECLINED
- PAYMENT_REFUNDED

**Schema** (Avro):
```json
{
  "type": "record",
  "name": "PaymentEvent",
  "fields": [
    {"name": "event_id", "type": "string"},
    {"name": "event_type", "type": "string"},
    {"name": "payment_id", "type": "long"},
    {"name": "order_id", "type": "long"},
    {"name": "transaction_id", "type": "string"},
    {"name": "amount", "type": {
      "type": "bytes",
      "logicalType": "decimal",
      "precision": 12,
      "scale": 2
    }},
    {"name": "currency", "type": "string"},
    {"name": "payment_method", "type": "string"},
    {"name": "gateway", "type": "string"},
    {"name": "status", "type": "string"},
    {"name": "decline_reason", "type": ["null", "string"], "default": null},
    {"name": "risk_score", "type": ["null", "int"], "default": null},
    {"name": "timestamp", "type": "long", "logicalType": "timestamp-millis"}
  ]
}
```

**Генерация**:
- **Throughput**: 30-150 events/second
- **Correlation**: Each payment generates 2-4 events (INITIATED → AUTHORIZED → CAPTURED)
- **Timing**: 
  - INITIATED → AUTHORIZED: 1-30 seconds
  - AUTHORIZED → CAPTURED: 1-60 seconds

**Decline rate**: 5% (generates PAYMENT_DECLINED instead of CAPTURED)

**Example**:
```json
{
  "event_id": "pay_evt_20250427_123456",
  "event_type": "PAYMENT_CAPTURED",
  "payment_id": 1234567,
  "order_id": 987654,
  "transaction_id": "TXN-STRIPE-20250427120534-a7b3c9",
  "amount": 45999,  // 459.99 in cents
  "currency": "USD",
  "payment_method": "CREDIT_CARD",
  "gateway": "stripe",
  "status": "SUCCESS",
  "decline_reason": null,
  "risk_score": 8,
  "timestamp": 1714228834123
}
```

---

### 4) Shipment Tracking

**Topic**: `techmart.shipments.tracking`

**Event Types**:
- LABEL_CREATED
- PICKED_UP
- IN_TRANSIT
- OUT_FOR_DELIVERY
- DELIVERED
- EXCEPTION

**Schema** (JSON):
```json
{
  "event_id": "string",
  "event_type": "string",
  "shipment_id": "integer",
  "order_id": "integer",
  "tracking_number": "string",
  "carrier": "string",
  "status": "string",
  "location": {
    "city": "string",
    "state": "string",
    "country": "string",
    "coordinates": {
      "lat": "number",
      "lon": "number"
    }
  },
  "timestamp": "string",
  "estimated_delivery": "string"
}
```

**Генерация**:
- **Throughput**: 10-50 events/second
- **Event sequence**: 5-8 events per shipment (tracking checkpoints)
- **Geographic progression**: Events follow shipping route

**Example**:
```json
{
  "event_id": "ship_evt_20250427_789012",
  "event_type": "IN_TRANSIT",
  "shipment_id": 567890,
  "order_id": 987654,
  "tracking_number": "FEDEX123456789012",
  "carrier": "FedEx",
  "status": "IN_TRANSIT",
  "location": {
    "city": "Memphis",
    "state": "TN",
    "country": "US",
    "coordinates": {
      "lat": 35.1495,
      "lon": -90.0490
    }
  },
  "timestamp": "2025-04-27T08:23:45Z",
  "estimated_delivery": "2025-04-29"
}
```

---

## 📊 Часть 6. Валюты и FX Rates

### Список валют

| Currency | Symbol | Base Countries | % of Transactions |
|----------|--------|----------------|-------------------|
| USD      | $      | US, CA         | 45%               |
| EUR      | €      | DE, FR, IT, ES | 25%               |
| GBP      | £      | GB             | 12%               |
| JPY      | ¥      | JP             | 10%               |
| CNY      | ¥      | CN             | 5%                |
| AUD      | A$     | AU             | 2%                |
| CAD      | C$     | CA             | 0.8%              |
| CHF      | CHF    | CH             | 0.2%              |

### FX Rates Generation Algorithm

**Base rates** (2025-01-01):
```python
BASE_RATES = {
    'USD_EUR': 0.9200,
    'USD_GBP': 0.7900,
    'USD_JPY': 145.50,
    'USD_CNY': 7.2500,
    'USD_AUD': 1.5200,
    'USD_CAD': 1.3500,
    'USD_CHF': 0.8800,
}
```

**Volatility parameters**:
```python
VOLATILITY = {
    'USD_EUR': 0.008,  # 0.8% daily
    'USD_GBP': 0.009,  # 0.9%
    'USD_JPY': 0.012,  # 1.2%
    'USD_CNY': 0.005,  # 0.5% (managed float)
    'USD_AUD': 0.015,  # 1.5%
    'USD_CAD': 0.010,  # 1.0%
    'USD_CHF': 0.007,  # 0.7%
}
```

**Generation formula**:
```python
import numpy as np
from datetime import datetime, timedelta

def generate_fx_rates(start_date, end_date, base_rate, volatility):
    """
    Geometric Brownian Motion for FX rates
    """
    dates = pd.date_range(start_date, end_date)
    n_days = len(dates)
    
    # Random walks
    returns = np.random.normal(0, volatility, n_days)
    
    # Add mean reversion (Ornstein-Uhlenbeck)
    mean_reversion_speed = 0.05
    for i in range(1, n_days):
        returns[i] += mean_reversion_speed * (0 - returns[i-1])
    
    # Calculate rates
    rates = base_rate * np.exp(np.cumsum(returns))
    
    # Add weekend gaps (rates don't change Sat-Sun)
    for i, date in enumerate(dates):
        if date.weekday() >= 5:  # Saturday or Sunday
            rates[i] = rates[i-1] if i > 0 else base_rate
    
    return pd.DataFrame({
        'rate_date': dates,
        'exchange_rate': rates
    })
```

**Cross-currency rates**:
```python
# All combinations generated through triangulation
# EUR/GBP = (USD/GBP) / (USD/EUR)
def triangulate(usd_eur, usd_gbp):
    return usd_gbp / usd_eur
```

**Market events simulation**:
```python
# Inject volatility spikes (simulate economic events)
EVENT_DATES = {
    '2024-11-05': {'volatility_multiplier': 3.0, 'reason': 'US Election'},
    '2024-12-18': {'volatility_multiplier': 1.5, 'reason': 'Fed Rate Decision'},
    '2025-03-20': {'volatility_multiplier': 2.0, 'reason': 'ECB Policy Change'},
}
```

**Missing data**:
- 0.2% missing (holidays: Christmas, New Year, national bank holidays)
- Handled by forward-fill

---

## 🧱 Часть 7. Технические требования к генераторам

### Configuration Format

**Master config** (`config/data_generation.yaml`):
```yaml
version: "1.0"
environment: "development"  # development | staging | production

seed: 42  # For deterministic generation

postgres:
  host: "localhost"
  port: 5432
  database: "techmart_oltp"
  schema: "public"

minio:
  endpoint: "localhost:9000"
  bucket: "techmart-data"
  access_key: "${MINIO_ACCESS_KEY}"
  secret_key: "${MINIO_SECRET_KEY}"

kafka:
  bootstrap_servers: "localhost:9092"
  schema_registry: "http://localhost:8081"

generation_rules:
  # OLTP
  customers:
    initial_count: 100000
    daily_increment: 1000
    error_rate: 0.02
    
  orders:
    initial_count: 500000
    daily_increment: 2500
    error_rate: 0.01
    seasonality_enabled: true
    
  # MinIO
  payment_files:
    frequency: "hourly"
    records_per_file: 10000
    error_rate: 0.005
    retention_days: 90
    
  # Kafka
  clickstream:
    throughput_per_second: 1000
    error_rate: 0.01
    peak_hours: [10, 11, 19, 20, 21]
    peak_multiplier: 2.0

quality:
  enable_errors: true
  enable_duplicates: true
  enable_late_arrivals: true
  
monitoring:
  metrics_port: 9090
  log_level: "INFO"
```

---

### Generator Interface

**Base generator class**:
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

class BaseDataGenerator(ABC):
    """
    Abstract base class for all data generators
    """
    
    def __init__(self, config: Dict[str, Any], seed: Optional[int] = None):
        self.config = config
        self.seed = seed or config.get('seed', 42)
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Set random seed for reproducibility
        np.random.seed(self.seed)
        random.seed(self.seed)
        
    @abstractmethod
    def generate(self, count: int, **kwargs) -> Any:
        """
        Generate data records
        
        Args:
            count: Number of records to generate
            **kwargs: Additional parameters
            
        Returns:
            Generated data (DataFrame, List, etc.)
        """
        pass
    
    @abstractmethod
    def validate(self, data: Any) -> bool:
        """
        Validate generated data
        
        Returns:
            True if valid, False otherwise
        """
        pass
    
    def inject_errors(self, data: Any, error_rate: float) -> Any:
        """
        Inject intentional errors for testing
        """
        pass
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Return generation metrics
        """
        return {
            'records_generated': self._records_generated,
            'errors_injected': self._errors_injected,
            'generation_time_ms': self._generation_time,
        }
```

---

### Idempotency Requirements

**Для OLTP generators**:
```python
class OrderGenerator(BaseDataGenerator):
    """
    Idempotent order generation
    """
    
    def generate(self, date: str, count: int):
        # Use date + seed для детерминизма
        day_seed = int(datetime.strptime(date, '%Y-%m-%d').timestamp())
        np.random.seed(self.seed + day_seed)
        
        # Generate orders for specific date
        orders = []
        for i in range(count):
            order_number = f"ORD-{date.replace('-', '')}-{i:06d}"
            # ... rest of generation
            
        return orders
    
    def backfill(self, start_date: str, end_date: str):
        """
        Re-generate historical data deterministically
        """
        dates = pd.date_range(start_date, end_date)
        for date in dates:
            orders = self.generate(
                date=date.strftime('%Y-%m-%d'),
                count=self._get_count_for_date(date)
            )
            self._upsert_to_db(orders)  # Upsert by order_number
```

---

### Inter-Generator Dependencies

**Dependency graph**:
```
currencies → fx_rates
    ↓
customers → addresses
    ↓
product_categories → sellers → products
    ↓
customers + products → carts → cart_items
    ↓
carts → orders → order_items
    ↓
orders → payments → refunds
    ↓
orders → shipments
```

**Execution order**:
```python
# Phase 1: Reference data
generators = [
    CurrencyGenerator(),
    ProductCategoryGenerator(),
    SellerGenerator(),
    PaymentMethodGenerator(),
    CarrierGenerator(),
]

# Phase 2: FX rates (time-series)
FXRateGenerator().generate_range(start_date, end_date)

# Phase 3: Core entities
CustomerGenerator().generate(100000)
ProductGenerator().generate(10000)

# Phase 4: Transactional (date-based)
for date in date_range(start_date, end_date):
    # New customers
    CustomerGenerator().generate_daily(date, count=1000)
    
    # Orders for the day
    orders = OrderGenerator().generate(date, count=2500)
    
    # Payments (same day or next)
    PaymentGenerator().generate_for_orders(orders)
    
    # Shipments (1-3 days later)
    ShipmentGenerator().generate_for_orders(orders)
```

---

### Schema Versioning

**Avro schema versioning**:
```json
{
  "type": "record",
  "name": "PaymentEvent",
  "namespace": "com.techmart.events.v2",
  "version": "2.0.0",
  "fields": [
    {"name": "event_id", "type": "string"},
    ...
    {
      "name": "billing_address",
      "type": ["null", {
        "type": "record",
        "name": "Address",
        "fields": [...]
      }],
      "default": null,
      "doc": "Added in v2.0.0"
    }
  ]
}
```

**Backward compatibility testing**:
```python
def test_schema_compatibility():
    """
    Ensure new schema can read old data
    """
    old_schema = load_schema('PaymentEvent_v1.avsc')
    new_schema = load_schema('PaymentEvent_v2.avsc')
    
    # Generate data with old schema
    old_data = generate_payment_event_v1()
    
    # Try to read with new schema
    reader = DataFileReader(old_data, DatumReader(new_schema))
    
    assert reader.read() is not None
```

---

### Monitoring and Metrics

**Prometheus metrics**:
```python
from prometheus_client import Counter, Histogram, Gauge

# Counters
records_generated = Counter(
    'data_generator_records_total',
    'Total records generated',
    ['generator', 'table']
)

errors_injected = Counter(
    'data_generator_errors_total',
    'Total errors injected',
    ['generator', 'error_type']
)

# Histogram
generation_duration = Histogram(
    'data_generator_duration_seconds',
    'Time spent generating data',
    ['generator']
)

# Gauge
current_throughput = Gauge(
    'data_generator_throughput',
    'Current generation rate (records/sec)',
    ['generator']
)
```

**Usage**:
```python
class OrderGenerator(BaseDataGenerator):
    
    @generation_duration.labels(generator='orders').time()
    def generate(self, count: int):
        orders = []
        for i in range(count):
            order = self._generate_single_order()
            orders.append(order)
            
            records_generated.labels(
                generator='orders',
                table='orders'
            ).inc()
            
        return orders
```

---

## 📄 Примеры использования

### 1. Initial seed (one-time)

```bash
# Generate reference data
python generators/seed_reference_data.py \
    --config config/data_generation.yaml \
    --seed 42

# Generate historical data (last 12 months)
python generators/backfill_historical.py \
    --start-date 2024-05-01 \
    --end-date 2025-04-27 \
    --config config/data_generation.yaml
```

---

### 2. Daily generation (cron job)

```bash
# Run daily at 01:00 UTC
0 1 * * * /app/generators/daily_generation.py --date $(date +\%Y-\%m-\%d)
```

**Script**:
```python
#!/usr/bin/env python3

import argparse
from generators import (
    CustomerGenerator,
    OrderGenerator,
    PaymentFileGenerator,
    ClickstreamProducer
)

def main(date: str):
    # New customers
    CustomerGenerator().generate_daily(date, count=1000)
    
    # Orders
    OrderGenerator().generate_daily(date)
    
    # Payment files to MinIO
    PaymentFileGenerator().generate_for_date(date)
    
    # Start Kafka producers (run in background)
    ClickstreamProducer().start()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', required=True)
    args = parser.parse_args()
    
    main(args.date)
```

---

### 3. Streaming simulation

```bash
# Start Kafka producers
python generators/kafka_producers.py \
    --topic clickstream \
    --throughput 1000 \
    --duration 3600  # 1 hour
```

---

## ✅ Validation Checklist

Перед использованием генераторы должны пройти:

- [ ] **Referential integrity**: All FKs valid
- [ ] **Data distribution**: Matches specified percentages
- [ ] **Temporal consistency**: Timestamps логичные (ordered_at < shipped_at)
- [ ] **Volume targets**: Correct record counts
- [ ] **Error injection**: Specified error rate achieved
- [ ] **Idempotency**: Re-running с same seed → same data
- [ ] **Schema compliance**: All fields match DDL
- [ ] **Performance**: Can generate 1M orders in < 5 min
- [ ] **Monitoring**: Metrics exported to Prometheus
- [ ] **Documentation**: README with examples

---

## Запуск streaming-генератора

Реализация каталога `generators/` упакована как Docker-сервис `data_generator`
с профилем `generators` (compose не поднимает её по умолчанию).

### Состав

- `generators/Dockerfile` — образ Python 3.11.
- `generators/generator.py` — долгоживущий runner (seed + tick loop).
- `generators/common/factories/` — фабрики справочников и событий.
- `generators/common/connectors/` — клиенты OLTP / Kafka / Redis / MinIO.
- `generators/common/schemas/` — JSON-схемы payload-ов.
- `generators/kafka/` — модули построения событий (orders, payments, clickstream).

### Конфигурация

Все параметры задаются в `.env` (есть пример в `.env.example`):

| Переменная | Назначение |
|------------|------------|
| `GENERATOR_TICK_SECONDS` | Период тика (сек). |
| `GENERATOR_SEED_USERS / SELLERS / PRODUCTS` | Размер seed-справочников. |
| `GENERATOR_ORDERS_PER_TICK_MIN/MAX` | Сколько заказов в тик. |
| `GENERATOR_CLICKS_PER_TICK_MIN/MAX` | Сколько clickstream-событий в тик. |
| `GENERATOR_MINIO_BATCH_TICKS` | Каждые N тиков выгружать batch-файлы в MinIO. |
| `GENERATOR_ENABLE_OLTP / KAFKA / REDIS / MINIO` | Включение каждого канала. |
| `KAFKA_TOPIC_*` | Имена топиков Kafka. |
| `REDIS_CHANNEL_* / REDIS_STREAM_ORDERS` | Pub/Sub-каналы и stream Redis. |
| `MINIO_BUCKET_RAW / MINIO_PREFIX_*` | Bucket и префиксы MinIO. |

### Команды запуска

```bash
cp .env.example .env

docker compose up -d postgres_oltp kafka redis minio

docker compose --profile generators build data_generator
docker compose --profile generators up -d data_generator

docker compose logs -f data_generator
```

Остановка только генератора:

```bash
docker compose --profile generators stop data_generator
```

### Проверка результатов

OLTP:

```bash
docker exec postgres_oltp psql -U oltp_user -d techmart_oltp \
  -c "SELECT 'users' t, COUNT(*) FROM users
      UNION ALL SELECT 'sellers', COUNT(*) FROM sellers
      UNION ALL SELECT 'products', COUNT(*) FROM products
      UNION ALL SELECT 'orders', COUNT(*) FROM orders
      UNION ALL SELECT 'order_items', COUNT(*) FROM order_items;"
```

Kafka:

```bash
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list | grep techmart

docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic techmart.events.orders --from-beginning --max-messages 3
```

Redis:

```bash
docker exec redis redis-cli XLEN techmart:stream:orders
docker exec redis redis-cli XREVRANGE techmart:stream:orders + - COUNT 1
docker exec redis redis-cli HGETALL techmart:counters:orders_by_country
```

MinIO (bucket `techmart-data`):

```bash
docker exec minio sh -c "ls -laR /data/techmart-data | head -40"
```

UI MinIO Console: <http://localhost:9001> (логин/пароль из `.env`,
по умолчанию `minio`/`minio123`).

### ER-диаграммы

Схемы для всех трёх каналов лежат в [`docs/diagrams`](./diagrams) в двух
форматах:

- Mermaid (`oltp-er.md`, `minio-er.md`, `kafka-er.md`).
- DBML (`oltp-er.dbml`, `minio-er.dbml`, `kafka-er.dbml`).

---

## 🎯 Заключение

Этот документ предоставляет **production-ready спецификацию** для генерации данных в TechMart pet-project.

**Ключевые принципы**:
1. **Реализм**: Данные отражают реальные e-commerce паттерны
2. **Сложность**: Достаточно сложные для демонстрации навыков DE
3. **Тестируемость**: Включены ошибки и edge cases
4. **Масштабируемость**: Генераторы работают с большими объемами
5. **Детерминизм**: Воспроизводимость через seed

**Следующие шаги**:
1. Имплементировать базовые генераторы (customers, products, orders)
2. Добавить MinIO file generators
3. Настроить Kafka producers
4. Интегрировать с Airflow для автоматизации
5. Добавить data quality checks
6. Создать monitoring dashboard

Этот фундамент позволит построить **реалистичную data platform** уровня middle+ data engineer.
