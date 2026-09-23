#!/usr/bin/env bash
# 호두랑 (withHodu): starts the app at http://localhost:8501. Options pass through, e.g. ./run.sh --server.port=8502
cd "$(dirname "$0")"

if lsof -ti:8501 >/dev/null 2>&1 && [[ "$*" != *server.port* ]]; then
    echo "8501 포트를 이미 쓰는 프로그램이 있어요. 호두랑이 켜져 있다면 http://localhost:8501 을 여세요." >&2
    echo "다른 포트로 켜려면: ./run.sh --server.port=8502" >&2
    exit 1
fi

exec python3 -m streamlit run app.py "$@"
