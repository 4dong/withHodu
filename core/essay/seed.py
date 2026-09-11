"""
Locates the optional, private essay seed/evaluation handoff folder.

The folder is never committed. Point ESSAY_SEED_DIR (environment or project .env) at it;
it is expected to contain data/seed.json and data/evaluation.json.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

SEED_DIR_ENV = "ESSAY_SEED_DIR"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_dotenv(name: str) -> Optional[str]:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return None
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    except OSError:
        return None
    return None


def seed_handoff_dir() -> Optional[Path]:
    """Returns the configured handoff folder, or None when unset or missing."""
    value = os.environ.get(SEED_DIR_ENV) or _read_dotenv(SEED_DIR_ENV)
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_dir() else None


def seed_data_file(name: str) -> Optional[Path]:
    """Returns <handoff>/data/<name> when it exists."""
    base = seed_handoff_dir()
    if base is None:
        return None
    path = base / "data" / name
    return path if path.is_file() else None
