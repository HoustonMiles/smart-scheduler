#!/bin/bash

echo "🚀 Starting Smart Scheduler in LOCAL mode..."

# Set environment
export ENV=local

# Check if .env.local exists
if [ ! -f backend/.env.local ]; then
    echo "❌ backend/.env.local not found!"
    echo "📝 Please create backend/.env.local with your Google OAuth credentials"
    exit 1
fi

# Build extension for local
./scripts/build-extension.sh local

# Check if virtual environment exists
if [ ! -d "backend/venv" ]; then
    echo "📦 Creating virtual environment..."
    cd backend && python3 -m venv venv && cd ..
fi

# Activate virtual environment
source backend/venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r backend/requirements.txt

# Run the FastAPI server
echo "🌐 Starting FastAPI server on http://localhost:8000"
echo "📌 OAuth callback URL: http://localhost:8000/callback"
echo ""
echo "⚠️  IMPORTANT: Make sure http://localhost:8000/callback is added"
echo "   to your Google OAuth Authorized Redirect URIs!"
echo ""
echo "🔧 Loading Chrome extension from: extension/"
echo "   Go to chrome://extensions/ and click 'Load unpacked'"
echo ""

cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
