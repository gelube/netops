#!/bin/sh
set -eu

PROJECT_DIR=/root/video-aggregator
BACKUP_DIR="$PROJECT_DIR/data/pg-backups"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT="$BACKUP_DIR/videohub_$STAMP.sql.gz"

mkdir -p "$BACKUP_DIR"
docker exec videohub-db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$OUTPUT"
find "$BACKUP_DIR" -type f -name 'videohub_*.sql.gz' -mtime "+$KEEP_DAYS" -delete

echo "Database backup created: $OUTPUT"
