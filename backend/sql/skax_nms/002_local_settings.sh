#!/bin/sh
set -eu

# The source login is named "cinamon", so its "$user" search path resolves to
# the cinamon schema. Reproduce that behavior for the local agent4any login.
psql \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=ON_ERROR_STOP=1 \
  --set=db_user="$POSTGRES_USER" \
  --set=db_name="$POSTGRES_DB" <<'SQL'
ALTER ROLE :"db_user" IN DATABASE :"db_name"
SET search_path TO cinamon, etc, public;
SQL
