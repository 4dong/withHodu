#!/usr/bin/env bash
# 호두랑 (withHodu) launch script
cd "$(dirname "$0")"

echo "🧹 Cleaning up existing Streamlit processes on port 8501..."
lsof -ti:8501 | xargs kill -9 2>/dev/null || true

echo "🐶 Starting 호두랑 (withHodu) on port 8501..."
python3 -m streamlit run app.py --server.port=8501 --server.runOnSave=true --server.fileWatcherType=poll
