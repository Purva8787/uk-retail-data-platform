-- =====================================================================
-- Albion Basket OLTP schema (3NF) - Module 4
-- Run order: this file is executed by ingestion/load_pg.py, or by hand:
--   psql -d albion -f sql/schema.sql
-- Re-runnable: drops and recreates the shop schema.
-- =====================================================================
DROP SCHEMA IF EXISTS shop CASCADE;
CREATE SCHEMA shop;
SET search_path TO shop;

-- Reference: one row per UK postcode area (e.g. 'SW', 'IV', 'BT').
-- region, nation and delivery_band all depend on the area and nothing else.
CREATE TABLE regions (
    postcode_area  VARCHAR(2)   PRIMARY KEY,
    region         VARCHAR(40)  NOT NULL,
    nation         VARCHAR(20)  NOT NULL
        CHECK (nation IN ('England', 'Scotland', 'Wales', 'Northern Ireland')),
    delivery_band  VARCHAR(20)  NOT NULL
        CHECK (delivery_band IN ('mainland', 'highlands_islands', 'northern_ireland'))
);

-- Reference: VAT rate per band, so the rate is stored once, not on every product.
CREATE TABLE vat_rates (
    vat_band  VARCHAR(10)   PRIMARY KEY CHECK (vat_band IN ('standard', 'reduced', 'zero')),
    rate      NUMERIC(4, 2) NOT NULL CHECK (rate >= 0 AND rate < 1)
);

-- An address is identified by its postcode; customers live at one and orders ship to one.
-- Keeping it separate means a gift order can ship somewhere other than the buyer's home.
CREATE TABLE addresses (
    address_id     SERIAL       PRIMARY KEY,
    postcode       VARCHAR(8)   NOT NULL UNIQUE
        CHECK (postcode ~ '^[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][ABD-HJLNP-UW-Z]{2}$'),
    postcode_area  VARCHAR(2)   NOT NULL REFERENCES regions (postcode_area)
);

CREATE TABLE customers (
    customer_id      INTEGER      PRIMARY KEY,
    full_name        VARCHAR(100) NOT NULL,
    email            VARCHAR(255) NOT NULL UNIQUE CHECK (email = lower(email)),
    home_address_id  INTEGER      NOT NULL REFERENCES addresses (address_id),
    signup_date      DATE         NOT NULL
);

CREATE TABLE products (
    sku             VARCHAR(20)    PRIMARY KEY,
    name            VARCHAR(120)   NOT NULL,
    category        VARCHAR(40)    NOT NULL,
    vat_band        VARCHAR(10)    NOT NULL REFERENCES vat_rates (vat_band),
    unit_price_gbp  NUMERIC(10, 2) NOT NULL CHECK (unit_price_gbp >= 0)   -- VAT-inclusive shelf price
);

CREATE TABLE orders (
    order_id             INTEGER        PRIMARY KEY,
    customer_id          INTEGER        NOT NULL REFERENCES customers (customer_id),
    delivery_address_id  INTEGER        NOT NULL REFERENCES addresses (address_id),
    order_ts             TIMESTAMPTZ    NOT NULL,
    channel              VARCHAR(20)    NOT NULL CHECK (channel IN ('web', 'ios_app', 'android_app')),
    total_gbp            NUMERIC(12, 2) NOT NULL CHECK (total_gbp >= 0),
    vat_gbp              NUMERIC(12, 2) NOT NULL CHECK (vat_gbp >= 0 AND vat_gbp <= total_gbp),
    delivery_fee_gbp     NUMERIC(6, 2)  NOT NULL CHECK (delivery_fee_gbp >= 0)  -- fee charged at the time
);

-- Price is stored on the line because it is the price *at the time of sale*,
-- which can differ from today's price in products.
CREATE TABLE order_items (
    order_id        INTEGER        NOT NULL REFERENCES orders (order_id) ON DELETE CASCADE,
    sku             VARCHAR(20)    NOT NULL REFERENCES products (sku),
    quantity        INTEGER        NOT NULL CHECK (quantity > 0),
    unit_price_gbp  NUMERIC(10, 2) NOT NULL CHECK (unit_price_gbp >= 0),
    PRIMARY KEY (order_id, sku)
);

CREATE INDEX ix_orders_customer ON orders (customer_id);
CREATE INDEX ix_orders_ts       ON orders (order_ts);
CREATE INDEX ix_items_sku       ON order_items (sku);

-- Convenience view: derived values (never stored, so they can't go stale).
CREATE VIEW v_orders AS
SELECT o.*,
       a.postcode,
       r.postcode_area,
       r.region,
       r.nation,
       r.delivery_band,
       o.total_gbp >= 500                         AS is_high_value,
       (o.order_ts AT TIME ZONE 'Europe/London')  AS order_ts_uk
FROM orders o
JOIN addresses a ON a.address_id = o.delivery_address_id
JOIN regions   r ON r.postcode_area = a.postcode_area;
