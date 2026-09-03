ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('admin', 'user', 'viewer'));

ALTER TABLE table_permissions DROP CONSTRAINT IF EXISTS table_permissions_role_check;
ALTER TABLE table_permissions ADD CONSTRAINT table_permissions_role_check
    CHECK (role IN ('admin', 'user', 'viewer'));
