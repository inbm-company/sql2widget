INSERT INTO categories (category_name, description) VALUES
    ('Beverages', 'Soft drinks and coffee'),
    ('Condiments', 'Sauces and seasonings'),
    ('Confections', 'Desserts and sweets')
ON CONFLICT (category_name) DO NOTHING;

INSERT INTO customers (customer_id, company_name, contact_name, country, city) VALUES
    ('ALFKI', 'Alfreds Futterkiste', 'Maria Anders', 'Germany', 'Berlin'),
    ('ANATR', 'Ana Trujillo Emparedados', 'Ana Trujillo', 'Mexico', 'Mexico City'),
    ('AROUT', 'Around the Horn', 'Thomas Hardy', 'UK', 'London'),
    ('BLAUS', 'Blauer See Delikatessen', 'Hanna Moos', 'Germany', 'Mannheim')
ON CONFLICT (customer_id) DO NOTHING;

INSERT INTO employees (first_name, last_name, title)
SELECT * FROM (VALUES
    ('Nancy', 'Davolio', 'Sales Representative'),
    ('Andrew', 'Fuller', 'Vice President, Sales'),
    ('Janet', 'Leverling', 'Sales Representative')
) AS v(first_name, last_name, title)
WHERE NOT EXISTS (SELECT 1 FROM employees LIMIT 1);

INSERT INTO products (product_name, category_id, unit_price, units_in_stock)
SELECT v.product_name, c.category_id, v.unit_price, v.units_in_stock
FROM (VALUES
    ('Chai', 'Beverages', 18.00::numeric, 39),
    ('Chang', 'Beverages', 19.00::numeric, 17),
    ('Aniseed Syrup', 'Condiments', 10.00::numeric, 13),
    ('Chef Anton''s Cajun Seasoning', 'Condiments', 22.00::numeric, 53),
    ('Chocolate Biscuits', 'Confections', 12.50::numeric, 30)
) AS v(product_name, category_name, unit_price, units_in_stock)
JOIN categories c ON c.category_name = v.category_name
WHERE NOT EXISTS (SELECT 1 FROM products LIMIT 1);

INSERT INTO orders (customer_id, employee_id, order_date, shipped_date, ship_country)
SELECT v.customer_id, e.employee_id, v.order_date::date, v.shipped_date::date, v.ship_country
FROM (VALUES
    ('ALFKI', 'Nancy', '2026-01-12', '2026-01-15', 'Germany'),
    ('ANATR', 'Andrew', '2026-02-04', '2026-02-08', 'Mexico'),
    ('AROUT', 'Janet', '2026-02-19', '2026-02-22', 'UK'),
    ('BLAUS', 'Nancy', '2026-03-07', '2026-03-10', 'Germany'),
    ('ALFKI', 'Andrew', '2026-03-22', '2026-03-25', 'Germany'),
    ('ANATR', 'Janet', '2026-04-11', '2026-04-14', 'Mexico')
) AS v(customer_id, employee_first_name, order_date, shipped_date, ship_country)
JOIN employees e ON e.first_name = v.employee_first_name
WHERE NOT EXISTS (SELECT 1 FROM orders LIMIT 1);

INSERT INTO order_details (order_id, product_id, unit_price, quantity, discount)
SELECT o.order_id, p.product_id, p.unit_price, v.quantity, v.discount
FROM (VALUES
    ('ALFKI', '2026-01-12', 'Chai', 10, 0.00::numeric),
    ('ALFKI', '2026-01-12', 'Chocolate Biscuits', 5, 0.05::numeric),
    ('ANATR', '2026-02-04', 'Chang', 8, 0.00::numeric),
    ('ANATR', '2026-02-04', 'Aniseed Syrup', 12, 0.10::numeric),
    ('AROUT', '2026-02-19', 'Chef Anton''s Cajun Seasoning', 7, 0.00::numeric),
    ('BLAUS', '2026-03-07', 'Chocolate Biscuits', 15, 0.00::numeric),
    ('ALFKI', '2026-03-22', 'Chai', 20, 0.05::numeric),
    ('ANATR', '2026-04-11', 'Chang', 18, 0.00::numeric)
) AS v(customer_id, order_date, product_name, quantity, discount)
JOIN orders o ON o.customer_id = v.customer_id AND o.order_date = v.order_date::date
JOIN products p ON p.product_name = v.product_name
WHERE NOT EXISTS (SELECT 1 FROM order_details LIMIT 1);
