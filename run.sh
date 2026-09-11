#!/usr/bin/env bash
# Antigravity Scholar Launch Script
cd "$(dirname "$0")"

echo "🧹 Cleaning up existing Streamlit processes on port 8501..."
lsof -ti:8501 | xargs kill -9 2>/dev/null || true

echo "🚀 Starting Antigravity Scholar Dashboard (Port 8501)..."
python3 -m streamlit run app.py --server.port=8501 --server.runOnSave=true --server.fileWatcherType=poll
