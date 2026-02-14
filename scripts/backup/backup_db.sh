#!/bin/bash

# Smart Scheduler Database Backup Script
# Usage: ./backup_db.sh [local|production]

set -e  # Exit on error

ENV=${1:-production}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "🔄 Starting backup for environment: $ENV"

# Load appropriate environment variables
if [ "$ENV" = "local" ]; then
    if [ -f .env.local ]; then
        export $(grep -v '^#' .env.local | xargs)
    else
        echo "❌ .env.local not found"
        exit 1
    fi
elif [ "$ENV" = "production" ]; then
    if [ -f .env.production ]; then
        export $(grep -v '^#' .env.production | xargs)
    else
        echo "❌ .env.production not found"
        echo "💡 Tip: Set DATABASE_URL environment variable manually"
        exit 1
    fi
fi

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL not set"
    exit 1
fi

# Extract connection details from DATABASE_URL
echo "🔍 Parsing connection details..."

# Use parameter expansion and sed to extract components
DB_USER=$(echo "$DATABASE_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASS=$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:/]*\).*|\1|p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_NAME=$(echo "$DATABASE_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

echo "🔍 DEBUG: User=$DB_USER Host=$DB_HOST Port=$DB_PORT DB=$DB_NAME"

# Generate backup filename
BACKUP_FILE="${BACKUP_DIR}/smart_scheduler_${ENV}_${TIMESTAMP}.dump"
echo "📦 Creating backup: $BACKUP_FILE"

# Export password for pg_dump
export PGPASSWORD="$DB_PASS"

# Perform backup with explicit connection parameters
pg_dump \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --format=custom \
    --verbose \
    --file="$BACKUP_FILE" \
    --no-owner \
    --no-acl

# Clear password from environment
unset PGPASSWORD

# Check if backup was successful
if [ $? -eq 0 ]; then
    FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ Backup completed successfully!"
    echo "📊 Backup size: $FILE_SIZE"
    echo "📁 Location: $BACKUP_FILE"
    
    # Create a "latest" symlink for easy access
    ln -sf "$(basename $BACKUP_FILE)" "${BACKUP_DIR}/smart_scheduler_${ENV}_latest.dump"
    echo "🔗 Latest backup linked to: smart_scheduler_${ENV}_latest.dump"
    
    # Cleanup old backups (keep last 7 days for daily, last 4 for weekly)
    echo "🧹 Cleaning up old backups..."
    find "$BACKUP_DIR" -name "smart_scheduler_${ENV}_*.dump" -type f -mtime +7 -delete
    
    echo ""
    echo "📋 Recent backups:"
    ls -lh "$BACKUP_DIR"/smart_scheduler_${ENV}_*.dump | tail -5
else
    echo "❌ Backup failed!"
    exit 1
fi
