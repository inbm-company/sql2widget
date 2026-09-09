-- Migrate legacy demo DB (sensors/site) before SOC schema seed

DROP TABLE IF EXISTS sensor_readings CASCADE;
DROP TABLE IF EXISTS sensors CASCADE;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'servers'
  ) THEN
    ALTER TABLE servers ADD COLUMN IF NOT EXISTS zone TEXT;
    ALTER TABLE servers ADD COLUMN IF NOT EXISTS criticality TEXT;
    ALTER TABLE servers ADD COLUMN IF NOT EXISTS owner TEXT;

    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'servers' AND column_name = 'site'
    ) THEN
      UPDATE servers SET zone = site WHERE zone IS NULL;
    END IF;

    UPDATE servers
    SET zone = COALESCE(zone, '본사'),
        criticality = COALESCE(criticality, 'medium')
    WHERE zone IS NULL OR criticality IS NULL;

    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'servers' AND column_name = 'site'
    ) THEN
      UPDATE servers SET site = COALESCE(site, zone) WHERE site IS NULL;
      ALTER TABLE servers ALTER COLUMN site DROP NOT NULL;
      ALTER TABLE servers DROP COLUMN site;
    END IF;

    IF (SELECT COUNT(*) FROM servers) <= 4 AND (SELECT COUNT(*) FROM attack_events) <= 10 THEN
      TRUNCATE attack_events RESTART IDENTITY CASCADE;
      TRUNCATE servers RESTART IDENTITY CASCADE;
    END IF;
  END IF;
END $$;
