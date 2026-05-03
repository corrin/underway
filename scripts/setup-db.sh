#!/usr/bin/env bash
# Create/refresh the local MariaDB user and databases for underway dev.
# Idempotent. Requires sudo access to the local MariaDB.
#
#   ./scripts/setup-db.sh
#   DB_PASSWORD='something-else' ./scripts/setup-db.sh

set -euo pipefail

DB_USER='underway'
DB_HOST='localhost'
DB_PASSWORD="${DB_PASSWORD:-underway-dev-pass}"

sudo mysql <<SQL
CREATE USER IF NOT EXISTS '${DB_USER}'@'${DB_HOST}' IDENTIFIED BY '${DB_PASSWORD}';
ALTER USER '${DB_USER}'@'${DB_HOST}' IDENTIFIED BY '${DB_PASSWORD}';
CREATE DATABASE IF NOT EXISTS underway_dev  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS underway_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL ON underway_dev.*  TO '${DB_USER}'@'${DB_HOST}';
GRANT ALL ON underway_test.* TO '${DB_USER}'@'${DB_HOST}';
SQL

if mysql -u "${DB_USER}" -h 127.0.0.1 -p"${DB_PASSWORD}" -e "SELECT 1;" >/dev/null 2>&1; then
  echo "OK: ${DB_USER}@${DB_HOST} connected; underway_dev and underway_test ready."
else
  echo "ERROR: setup ran but ${DB_USER} can't connect with the given password." >&2
  exit 1
fi
