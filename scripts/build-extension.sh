#!/bin/bash

ENV=$1

if [ -z "$ENV" ]; then
    echo "Usage: ./build-extension.sh [local|production]"
    exit 1
fi

cd extension

if [ "$ENV" = "local" ]; then
    echo "🏗️  Building for LOCAL development..."
    cp manifest.local.json manifest.json
    # Update API_BASE in src/background.js
    sed -i '' 's|const API_BASE = ".*"|const API_BASE = "http://localhost:8000"|g' src/background.js
    sed -i '' 's|const API_BASE = ".*"|const API_BASE = "http://localhost:8000"|g' src/sidepanel.js
    echo "✅ Local build complete!"
    echo "📍 API pointing to: http://localhost:8000"
elif [ "$ENV" = "production" ]; then
    echo "🏗️  Building for PRODUCTION..."
    cp manifest.production.json manifest.json
    # Update API_BASE in src/background.js
    sed -i '' 's|const API_BASE = ".*"|const API_BASE = "https://smart-scheduler-production-3978.up.railway.app"|g' src/background.js
    sed -i '' 's|const API_BASE = ".*"|const API_BASE = "https://smart-scheduler-production-3978.up.railway.app"|g' src/sidepanel.js
    echo "✅ Production build complete!"
    echo "📍 API pointing to: https://smart-scheduler-production-3978.up.railway.app"
else
    echo "❌ Invalid environment. Use 'local' or 'production'"
    exit 1
fi

echo ""
echo "📦 Extension ready in: extension/"
echo "💡 Load unpacked extension from Chrome Extensions page"
