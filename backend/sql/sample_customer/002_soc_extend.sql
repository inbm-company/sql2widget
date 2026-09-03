-- Extended SOC tables and seed data

CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    severity TEXT NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL,
    asset_id INT REFERENCES servers(id)
);

CREATE TABLE IF NOT EXISTS vulnerability_findings (
    id SERIAL PRIMARY KEY,
    cve TEXT NOT NULL,
    asset_id INT NOT NULL REFERENCES servers(id),
    score NUMERIC(4, 1) NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blocked_ips (
    id SERIAL PRIMARY KEY,
    ip INET NOT NULL,
    reason TEXT NOT NULL,
    blocked_at TIMESTAMPTZ NOT NULL,
    hit_count INT NOT NULL DEFAULT 1
);

INSERT INTO incidents (title, status, severity, opened_at, asset_id)
SELECT m.title, m.status, m.severity, now() - (m.days || ' days')::interval, s.id
FROM (
    VALUES
        ('web-prod-01 SSH brute force surge', 'investigating', 'high', 3, 'web-prod-01'),
        ('Ransomware alert on web-prod-02', 'open', 'critical', 5, 'web-prod-02'),
        ('api-core-01 SQL injection attempt', 'closed', 'high', 12, 'api-core-01'),
        ('DDoS on api-core-02', 'investigating', 'high', 2, 'api-core-02'),
        ('db-primary-01 privilege escalation', 'open', 'critical', 8, 'db-primary-01'),
        ('bastion-01 repeated login failures', 'closed', 'medium', 15, 'bastion-01'),
        ('vpn-gw-01 traffic anomaly', 'investigating', 'high', 1, 'vpn-gw-01'),
        ('worker-cloud-01 cryptomining detected', 'closed', 'medium', 20, 'worker-cloud-01')
) AS m(title, status, severity, days, hostname)
JOIN servers s ON s.hostname = m.hostname
WHERE NOT EXISTS (SELECT 1 FROM incidents LIMIT 1);

INSERT INTO vulnerability_findings (cve, asset_id, score, status)
SELECT m.cve, s.id, m.score, m.status
FROM (
    VALUES
        ('CVE-2024-1234', 'web-prod-01', 9.8, 'open'),
        ('CVE-2024-5678', 'web-prod-01', 7.5, 'mitigated'),
        ('CVE-2023-9012', 'web-prod-02', 8.1, 'open'),
        ('CVE-2024-3456', 'api-core-01', 6.4, 'open'),
        ('CVE-2024-7890', 'api-core-02', 5.9, 'accepted'),
        ('CVE-2023-2345', 'db-primary-01', 9.1, 'open'),
        ('CVE-2024-6789', 'bastion-01', 4.3, 'mitigated'),
        ('CVE-2024-1111', 'worker-cloud-01', 7.2, 'open'),
        ('CVE-2024-2222', 'worker-cloud-02', 6.8, 'open'),
        ('CVE-2023-3333', 'mail-relay-01', 5.1, 'mitigated'),
        ('CVE-2024-4444', 'vpn-gw-01', 8.7, 'open'),
        ('CVE-2024-5555', 'api-core-01', 4.0, 'accepted')
) AS m(cve, hostname, score, status)
JOIN servers s ON s.hostname = m.hostname
WHERE NOT EXISTS (SELECT 1 FROM vulnerability_findings LIMIT 1);

INSERT INTO blocked_ips (ip, reason, blocked_at, hit_count)
SELECT * FROM (VALUES
    ('203.0.113.10'::inet, 'SSH brute force', now() - interval '2 days', 842),
    ('198.51.100.44'::inet, 'SQL injection probe', now() - interval '5 days', 156),
    ('192.0.2.88'::inet, 'Port scan', now() - interval '1 day', 1204),
    ('203.0.113.55'::inet, 'DDoS source', now() - interval '3 days', 5021),
    ('198.51.100.91'::inet, 'Phishing callback', now() - interval '7 days', 89),
    ('192.0.2.17'::inet, 'Ransomware C2', now() - interval '4 days', 34),
    ('203.0.113.72'::inet, 'Brute force SSH', now() - interval '6 hours', 412),
    ('198.51.100.33'::inet, 'Spam relay', now() - interval '10 days', 67),
    ('192.0.2.99'::inet, 'Cryptomining pool', now() - interval '8 days', 203),
    ('203.0.113.21'::inet, 'VPN abuse', now() - interval '12 days', 55)
) AS v(ip, reason, blocked_at, hit_count)
WHERE NOT EXISTS (SELECT 1 FROM blocked_ips LIMIT 1);
