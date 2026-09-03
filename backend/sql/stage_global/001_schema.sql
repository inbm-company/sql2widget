CREATE TABLE IF NOT EXISTS regions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monthly_sales (
    id TEXT PRIMARY KEY,
    region_id TEXT NOT NULL REFERENCES regions(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    month DATE NOT NULL,
    revenue NUMERIC(14, 2) NOT NULL DEFAULT 0,
    units INT NOT NULL DEFAULT 0,
    UNIQUE (region_id, product_id, month)
);

CREATE INDEX IF NOT EXISTS idx_monthly_sales_month ON monthly_sales(month);
CREATE INDEX IF NOT EXISTS idx_monthly_sales_region ON monthly_sales(region_id);
