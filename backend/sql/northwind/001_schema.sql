-- Small Northwind-style PostgreSQL fixture for generic-schema agent testing.
CREATE TABLE IF NOT EXISTS categories (
    category_id SERIAL PRIMARY KEY,
    category_name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    contact_name TEXT,
    country TEXT,
    city TEXT
);

CREATE TABLE IF NOT EXISTS employees (
    employee_id SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    title TEXT
);

CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    product_name TEXT NOT NULL,
    category_id INT REFERENCES categories(category_id),
    unit_price NUMERIC(12, 2) NOT NULL,
    units_in_stock INT NOT NULL DEFAULT 0,
    discontinued BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS orders (
    order_id SERIAL PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    employee_id INT REFERENCES employees(employee_id),
    order_date DATE NOT NULL,
    shipped_date DATE,
    ship_country TEXT
);

CREATE TABLE IF NOT EXISTS order_details (
    order_id INT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES products(product_id),
    unit_price NUMERIC(12, 2) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    discount NUMERIC(5, 2) NOT NULL DEFAULT 0 CHECK (discount >= 0 AND discount < 1),
    PRIMARY KEY (order_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_order_details_product ON order_details(product_id);
