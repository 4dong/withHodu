"""
Backup and Restore Manager for Essay Archive (Database and Sources).
"""

from __future__ import annotations
import os
import sqlite3
import zipfile
from pathlib import Path
from typing import Dict, Any

from core.essay.repository import EssayRepository, utc_now_iso


class EssayBackupService:
    @staticmethod
    def create_backup(repo: EssayRepository, dest_zip_path: Path) -> Dict[str, Any]:
        """
        Creates an atomic backup ZIP including SQLite WAL checkpointed database
        and all raw source files.
        """
        dest_zip_path.parent.mkdir(parents=True, exist_ok=True)
        temp_db_copy = repo.temp_dir / f"backup_{os.urandom(4).hex()}.db"

        # Safely copy SQLite database using online backup API
        with repo.get_connection() as src_conn:
            bck_conn = sqlite3.connect(str(temp_db_copy))
            src_conn.backup(bck_conn)
            bck_conn.close()

        file_count = 0
        total_bytes = 0

        with zipfile.ZipFile(dest_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add DB
            zf.write(temp_db_copy, arcname="db/essay_archive.db")

            # Add source files
            for root, _, files in os.walk(repo.sources_dir):
                for f in files:
                    full_p = Path(root) / f
                    rel_p = full_p.relative_to(repo.sources_dir)
                    zf.write(full_p, arcname=f"sources/{rel_p}")
                    file_count += 1
                    total_bytes += full_p.stat().st_size

        if temp_db_copy.exists():
            temp_db_copy.unlink()

        return {
            "backup_path": str(dest_zip_path),
            "sources_count": file_count,
            "total_bytes": total_bytes,
            "created_at": utc_now_iso()
        }

    @staticmethod
    def restore_backup(backup_zip_path: Path, target_repo_root: Path) -> EssayRepository:
        """
        Restores an archive backup ZIP into target_repo_root and verifies integrity.
        """
        target_repo_root = Path(target_repo_root).resolve()
        target_repo_root.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(backup_zip_path, "r") as zf:
            zf.extractall(target_repo_root)

        # Initialize repository on restored root
        repo = EssayRepository(archive_root=str(target_repo_root))

        # Integrity check
        with repo.get_connection() as conn:
            cur = conn.execute("PRAGMA integrity_check;")
            row = cur.fetchone()
            if not row or row[0] != "ok":
                raise ValueError(f"복원된 SQLite 데이터베이스 무결성 오류: {row}")

        return repo
