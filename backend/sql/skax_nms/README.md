# SKAX NMS fixture

`001_full_dump.sql.gz` is a one-time snapshot of
`www_5013_skax_nms_20260327`. It includes all non-system schemas and table data
because objects in `cinamon` depend on relations in `etc`. Source ownership and
grants are excluded so the local PostgreSQL user owns the restored objects. The
sql2widget connection exposes the `cinamon` tables and views.

`002_local_settings.sh` gives the local database user the source-equivalent
`cinamon, etc, public` search path. This is required by restored functions that
use unqualified relation names.

Docker Compose restores this file only when the `pg_skax_nms_data` volume is
created for the first time. To refresh the snapshot, create a new dump and then
recreate only that volume intentionally; do not remove unrelated service
volumes.
