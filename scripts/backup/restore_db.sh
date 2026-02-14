#!/bin/bash

# Smart Scheduler Database Restore Script
# Usage: ./restore_db.sh [backup_file] [environment]

set -e

BACKUP_FILE=$1
ENV=${2:-production}

if [ -z "$BACKUP_FILE" ]; then
    echo "❌ Usage: ./restore_db.sh <backup_file> [local|production]"
    echo ""
    echo "📁 Available backups:"
    ls -lh ./backups/*.dump 2>/dev/null || echo "No backups found"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "⚠️  WARNING: This will REPLACE the current database!"
echo "📁 Backup file: $BACKUP_FILE"
echo "🌍 Environment: $ENV"
echo ""
read -p "Are you sure you want to continue? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "❌ Restore cancelled"
    exit 0
fi

# Load environment variables
if [ "$ENV" = "local" ]; then
    if [ -f .env.local ]; then
        export $(grep -v '^#' .env.local | xargs)
    fi
elif [ "$ENV" = "production" ]; then
    if [ -f .env.production ]; then
        export $(grep -v '^#' .env.production | xargs)
    fi
fi

if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL not set"
    exit 1
fi

# Extract connection details from DATABASE_URL
echo "🔍 Parsing connection details..."
DB_USER=$(echo "$DATABASE_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASS=$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:/]*\).*|\1|p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_NAME=$(echo "$DATABASE_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

echo "🔄 Starting restore..."

# Export password for pg_restore
export PGPASSWORD="$DB_PASS"

# Restore the database
pg_restore \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --clean \
    --if-exists \
    --no-owner \
    --no-acl \
    --verbose \
    "$BACKUP_FILE"

# Clear password from environment
unset PGPASSWORD

if [ $? -eq 0 ]; then
    echo "✅ Restore completed successfully!"
    echo ""
    echo "🔍 Verifying restore..."
    
    # Export password again for psql
    export PGPASSWORD="$DB_PASS"
    
    # Verify by counting records
    psql \
        --host="$DB_HOST" \
        --port="$DB_PORT" \
        --username="$DB_USER" \
        --dbname="$DB_NAME" \
        -c "SELECT 'tasks' as table_name, COUNT(*) as count FROM tasks 
            UNION ALL 
            SELECT 'calendar_events', COUNT(*) FROM calendar_events 
            UNION ALL 
            SELECT 'user_settings', COUNT(*) FROM user_settings
            UNION ALL
            SELECT 'users', COUNT(*) FROM users;"
    
    unset PGPASSWORD
    
    echo ""
    echo "✅ Database restored and verified!"
else
    echo "❌ Restore failed!"
    exit 1
fi
