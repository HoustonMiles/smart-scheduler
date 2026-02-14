#!/bin/bash

# Database Verification Script
# Usage: ./verify_db.sh [local|production]

ENV=${1:-production}

echo "🔍 Verifying database integrity for: $ENV"

# Load environment
if [ "$ENV" = "local" ]; then
    [ -f .env.local ] && export $(grep -v '^#' .env.local | xargs)
elif [ "$ENV" = "production" ]; then
    [ -f .env.production ] && export $(grep -v '^#' .env.production | xargs)
fi

if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL not set"
    exit 1
fi

# Extract connection details from DATABASE_URL
DB_USER=$(echo "$DATABASE_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASS=$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:/]*\).*|\1|p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_NAME=$(echo "$DATABASE_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

# Export password for psql
export PGPASSWORD="$DB_PASS"

echo ""
echo "📊 Database Statistics:"
echo "======================"

# Run all verification queries
psql \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
<<EOF
-- Record counts
SELECT 
    'users' as table_name,
    COUNT(*) as total_records,
    NULL as pending,
    NULL as completed
FROM users
UNION ALL
SELECT 
    'tasks' as table_name, 
    COUNT(*) as total_records,
    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed
FROM tasks
UNION ALL
SELECT 
    'calendar_events', 
    COUNT(*),
    NULL,
    NULL
FROM calendar_events
UNION ALL
SELECT 
    'user_settings', 
    COUNT(*),
    NULL,
    NULL
FROM user_settings;

-- Recent tasks
\echo ''
\echo '📅 Recent Tasks:'
\echo '================'
SELECT id, title, due_date, status, priority 
FROM tasks 
ORDER BY due_date DESC 
LIMIT 5;

-- Database size
\echo ''
\echo '💾 Database Size:'
\echo '================='
SELECT pg_size_pretty(pg_database_size(current_database())) as size;

-- Table sizes
\echo ''
\echo '📦 Table Sizes:'
\echo '==============='
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
EOF

# Clear password from environment
unset PGPASSWORD

echo ""
echo "✅ Verification complete!"
