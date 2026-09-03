INSERT INTO regions (id, name, code, latitude, longitude) VALUES
    ('reg_na', 'North America', 'NA', 40.0, -100.0),
    ('reg_emea', 'EMEA', 'EMEA', 50.0, 10.0),
    ('reg_apac', 'Asia Pacific', 'APAC', 15.0, 105.0),
    ('reg_latam', 'Latin America', 'LATAM', -15.0, -60.0),
    ('reg_me', 'Middle East', 'ME', 25.0, 45.0),
    ('reg_oce', 'Oceania', 'OCE', -25.0, 135.0)
ON CONFLICT (id) DO NOTHING;

INSERT INTO products (id, name, category) VALUES
    ('prd_cloud', 'Cloud Platform', 'SaaS'),
    ('prd_sec', 'Security Suite', 'Security'),
    ('prd_analytics', 'Analytics Pro', 'Analytics'),
    ('prd_support', 'Support Services', 'Services')
ON CONFLICT (id) DO NOTHING;

INSERT INTO monthly_sales (id, region_id, product_id, month, revenue, units)
SELECT
    'ms_' || substr(md5(r.id || p.id || m.month::text), 1, 12),
    r.id,
    p.id,
    m.month,
    ROUND(
        (120000 + abs(hashtext(r.id || p.id || m.month::text)) % 380000)::numeric
        + (extract(month from m.month) * 4200),
        2
    ),
    40 + (abs(hashtext(p.id || m.month::text)) % 260)
FROM regions r
CROSS JOIN products p
CROSS JOIN generate_series(
    date_trunc('month', CURRENT_DATE - interval '11 months'),
    date_trunc('month', CURRENT_DATE),
    interval '1 month'
) AS m(month)
ON CONFLICT (region_id, product_id, month) DO NOTHING;
