-- SOC demo customer DB (security-only domain)

CREATE TABLE IF NOT EXISTS servers (
    id SERIAL PRIMARY KEY,
    hostname TEXT NOT NULL,
    zone TEXT NOT NULL,
    criticality TEXT NOT NULL DEFAULT 'medium',
    owner TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS attack_events (
    id SERIAL PRIMARY KEY,
    server_id INT NOT NULL REFERENCES servers(id),
    attack_method TEXT NOT NULL,
    severity TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL
);

INSERT INTO servers (hostname, zone, criticality, owner)
SELECT * FROM (VALUES
    ('web-prod-01', 'DMZ', 'high', 'platform-team'),
    ('web-prod-02', 'DMZ', 'high', 'platform-team'),
    ('api-core-01', '본사', 'critical', 'backend-team'),
    ('api-core-02', '본사', 'critical', 'backend-team'),
    ('db-primary-01', '본사', 'critical', 'dba-team'),
    ('bastion-01', 'DMZ', 'high', 'infra-team'),
    ('worker-cloud-01', '클라우드', 'medium', 'data-team'),
    ('worker-cloud-02', '클라우드', 'medium', 'data-team'),
    ('mail-relay-01', '본사', 'medium', 'infra-team'),
    ('vpn-gw-01', 'DMZ', 'high', 'network-team')
) AS v(hostname, zone, criticality, owner)
WHERE NOT EXISTS (SELECT 1 FROM servers LIMIT 1);

INSERT INTO attack_events (server_id, attack_method, severity, occurred_at)
SELECT s.id, m.method, m.severity, now() - (m.days || ' days')::interval - (m.hours || ' hours')::interval
FROM servers s
JOIN (
    VALUES
        ('web-prod-01', 'Brute Force SSH', 'high', 35, 2),
        ('web-prod-01', 'Brute Force SSH', 'high', 28, 5),
        ('web-prod-01', 'SQL Injection', 'medium', 22, 1),
        ('web-prod-01', 'Port Scan', 'low', 15, 3),
        ('web-prod-02', 'Ransomware', 'critical', 40, 4),
        ('web-prod-02', 'Phishing Callback', 'medium', 33, 6),
        ('web-prod-02', 'Brute Force SSH', 'high', 25, 2),
        ('api-core-01', 'SQL Injection', 'high', 38, 8),
        ('api-core-01', 'Brute Force SSH', 'high', 30, 1),
        ('api-core-01', 'Port Scan', 'low', 18, 4),
        ('api-core-02', 'DDoS', 'high', 42, 12),
        ('api-core-02', 'Brute Force SSH', 'high', 20, 3),
        ('db-primary-01', 'SQL Injection', 'critical', 45, 6),
        ('db-primary-01', 'Privilege Escalation', 'critical', 12, 2),
        ('bastion-01', 'Brute Force SSH', 'high', 10, 5),
        ('bastion-01', 'Brute Force SSH', 'high', 7, 1),
        ('bastion-01', 'Port Scan', 'low', 5, 8),
        ('worker-cloud-01', 'Port Scan', 'low', 55, 2),
        ('worker-cloud-01', 'Cryptomining', 'medium', 48, 4),
        ('worker-cloud-02', 'Port Scan', 'low', 50, 3),
        ('worker-cloud-02', 'Brute Force SSH', 'medium', 14, 7),
        ('mail-relay-01', 'Phishing Callback', 'medium', 32, 9),
        ('mail-relay-01', 'Spam Relay', 'low', 26, 11),
        ('vpn-gw-01', 'DDoS', 'high', 8, 6),
        ('vpn-gw-01', 'Brute Force SSH', 'high', 3, 2),
        ('web-prod-01', 'Brute Force SSH', 'high', 2, 4),
        ('api-core-01', 'Port Scan', 'low', 1, 1),
        ('web-prod-02', 'Port Scan', 'low', 60, 5),
        ('db-primary-01', 'Brute Force SSH', 'high', 55, 3),
        ('worker-cloud-01', 'Brute Force SSH', 'medium', 4, 2)
) AS m(hostname, method, severity, days, hours)
  ON s.hostname = m.hostname
WHERE NOT EXISTS (SELECT 1 FROM attack_events LIMIT 1);
