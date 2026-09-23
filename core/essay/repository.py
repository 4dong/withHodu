"""
SQLite Repository and Storage Manager for the Essay Archive System.
"""

from __future__ import annotations
import os
import re
import sqlite3
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from core.essay.models import (
    Document, SourceFile, Answer, AnswerRevision,
    SourceSpan, Tag, TagAssignment, Job,
    new_uuid, utc_now_iso
)
from core.essay.seed import PROJECT_ROOT, seed_handoff_dir

DEFAULT_ESSAY_ARCHIVE_ROOT = os.path.expanduser(
    os.environ.get("ESSAY_ARCHIVE_ROOT", "~/EssayArchive")
)


class EssayRepository:
    CURRENT_SCHEMA_VERSION = 1

    def __init__(self, archive_root: Optional[str] = None):
        self.archive_root = Path(archive_root or DEFAULT_ESSAY_ARCHIVE_ROOT).resolve()
        self.db_dir = self.archive_root / "db"
        self.sources_dir = self.archive_root / "sources"
        self.exports_dir = self.archive_root / "exports"
        self.temp_dir = self.archive_root / "temp"
        self.documents_dir = self.archive_root / "documents"

        # Ensure directory structure
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.db_dir / "essay_archive.db"
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
            """)
            cur = conn.execute("SELECT MAX(version) FROM schema_migrations;")
            row = cur.fetchone()
            current_v = row[0] if (row and row[0] is not None) else 0

            if current_v < 1:
                self._apply_migration_v1(conn)
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?);",
                    (1, utc_now_iso())
                )
            conn.commit()

    def _apply_migration_v1(self, conn: sqlite3.Connection):
        """Initial schema creation."""
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                division TEXT NOT NULL,
                role TEXT NOT NULL,
                collection TEXT NOT NULL DEFAULT 'reference',
                author TEXT,
                recruitment_year INTEGER,
                outcome TEXT NOT NULL DEFAULT 'unknown',
                grouping_status TEXT NOT NULL DEFAULT 'provisional',
                completeness TEXT NOT NULL DEFAULT 'unknown',
                notes TEXT,
                deleted_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_files (
                id TEXT PRIMARY KEY,
                content_sha256 TEXT UNIQUE NOT NULL,
                original_name TEXT NOT NULL,
                media_type TEXT NOT NULL,
                storage_key TEXT NOT NULL,
                byte_size INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pages (
                id TEXT PRIMARY KEY,
                source_file_id TEXT NOT NULL REFERENCES source_files(id) ON DELETE RESTRICT,
                physical_page INTEGER NOT NULL,
                orientation INTEGER NOT NULL DEFAULT 0,
                preprocessing_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                UNIQUE(source_file_id, physical_page)
            );

            CREATE TABLE IF NOT EXISTS document_pages (
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE RESTRICT,
                order_index INTEGER NOT NULL,
                page_kind TEXT NOT NULL DEFAULT 'answer',
                PRIMARY KEY (document_id, page_id)
            );

            CREATE TABLE IF NOT EXISTS answers (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                question_number INTEGER NOT NULL,
                current_revision_id TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(document_id, question_number)
            );

            CREATE TABLE IF NOT EXISTS answer_revisions (
                id TEXT PRIMARY KEY,
                answer_id TEXT NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
                parent_revision_id TEXT REFERENCES answer_revisions(id) ON DELETE SET NULL,
                question_text TEXT NOT NULL,
                body_text TEXT NOT NULL,
                text_sha256 TEXT NOT NULL,
                origin TEXT NOT NULL DEFAULT 'manual',
                review_status TEXT NOT NULL DEFAULT 'needs_user_review',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_spans (
                id TEXT PRIMARY KEY,
                revision_id TEXT NOT NULL REFERENCES answer_revisions(id) ON DELETE CASCADE,
                start_char INTEGER NOT NULL,
                end_char INTEGER NOT NULL,
                page_id TEXT REFERENCES pages(id) ON DELETE SET NULL,
                source_id TEXT,
                bbox_json TEXT,
                uncertain INTEGER NOT NULL DEFAULT 0,
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS tags (
                canonical_id TEXT PRIMARY KEY,
                facet TEXT NOT NULL,
                label TEXT NOT NULL,
                UNIQUE(facet, label)
            );

            CREATE TABLE IF NOT EXISTS tag_aliases (
                alias TEXT PRIMARY KEY,
                canonical_id TEXT NOT NULL REFERENCES tags(canonical_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tag_assignments (
                id TEXT PRIMARY KEY,
                target_id TEXT NOT NULL,
                target_type TEXT NOT NULL,
                tag_id TEXT NOT NULL REFERENCES tags(canonical_id) ON DELETE CASCADE,
                origin TEXT NOT NULL DEFAULT 'manual',
                status TEXT NOT NULL DEFAULT 'suggested',
                evidence_quote TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(target_id, tag_id)
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                revision_id TEXT NOT NULL REFERENCES answer_revisions(id) ON DELETE CASCADE,
                answer_id TEXT NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                start_char INTEGER NOT NULL,
                end_char INTEGER NOT NULL,
                kind TEXT NOT NULL DEFAULT 'answer',
                text TEXT NOT NULL,
                index_generation TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS embeddings (
                chunk_id TEXT PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                model_id TEXT NOT NULL,
                dimension INTEGER NOT NULL,
                task_config_hash TEXT NOT NULL,
                vector BLOB NOT NULL,
                index_generation TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                target_id TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                config_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                attempt INTEGER NOT NULL DEFAULT 0,
                lease_until TEXT,
                progress REAL NOT NULL DEFAULT 0.0,
                error_code TEXT,
                error_message TEXT,
                result_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS style_profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                features_json TEXT NOT NULL,
                reference_revision_ids_json TEXT NOT NULL,
                extractor_version INTEGER NOT NULL DEFAULT 1,
                accepted_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rewrite_proposals (
                id TEXT PRIMARY KEY,
                input_revision_id TEXT NOT NULL REFERENCES answer_revisions(id) ON DELETE CASCADE,
                output_text TEXT NOT NULL,
                profile_id TEXT REFERENCES style_profiles(id) ON DELETE SET NULL,
                facts_json TEXT NOT NULL,
                diff_json TEXT NOT NULL,
                validation_json TEXT NOT NULL,
                model_config TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'suggested',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS index_generations (
                id TEXT PRIMARY KEY,
                config_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'building',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS seed_imports (
                external_id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                internal_id TEXT NOT NULL,
                imported_at TEXT NOT NULL
            );

            -- Indices
            CREATE INDEX IF NOT EXISTS idx_documents_company ON documents(company);
            CREATE INDEX IF NOT EXISTS idx_documents_deleted ON documents(deleted_at);
            CREATE INDEX IF NOT EXISTS idx_answers_doc ON answers(document_id);
            CREATE INDEX IF NOT EXISTS idx_revisions_answer ON answer_revisions(answer_id);
            CREATE INDEX IF NOT EXISTS idx_chunks_revision ON chunks(revision_id);
            CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        """)

        # FTS5 Trigram table for Korean/English/Alphanumeric text search
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    chunk_id UNINDEXED,
                    document_id UNINDEXED,
                    answer_id UNINDEXED,
                    revision_id UNINDEXED,
                    text,
                    tokenize='trigram'
                );
            """)
        except Exception:
            # Fallback to standard fts5 if trigram is unavailable on system sqlite3
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    chunk_id UNINDEXED,
                    document_id UNINDEXED,
                    answer_id UNINDEXED,
                    revision_id UNINDEXED,
                    text
                );
            """)

    # -------------------------------------------------------------------------
    # Source File Storage Management
    # -------------------------------------------------------------------------
    def store_source_file(
        self,
        file_bytes: bytes,
        original_name: str,
        media_type: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> SourceFile:
        """Stores a source file atomically with deduplication by sha256."""
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        byte_size = len(file_bytes)

        managed_conn = False
        if conn is None:
            conn = self.get_connection()
            managed_conn = True

        try:
            cur = conn.execute(
                "SELECT id, content_sha256, original_name, media_type, storage_key, byte_size, created_at FROM source_files WHERE content_sha256 = ?",
                (sha256,)
            )
            row = cur.fetchone()
            if row:
                return SourceFile(
                    id=row["id"],
                    content_sha256=row["content_sha256"],
                    original_name=row["original_name"],
                    media_type=row["media_type"],
                    storage_key=row["storage_key"],
                    byte_size=row["byte_size"],
                    created_at=row["created_at"]
                )

            file_id = new_uuid()
            ext = Path(original_name).suffix.lower() or ".bin"
            prefix = sha256[:2]
            dest_dir = self.sources_dir / prefix
            dest_dir.mkdir(parents=True, exist_ok=True)
            storage_filename = f"{sha256}{ext}"
            final_path = dest_dir / storage_filename
            storage_key = f"{prefix}/{storage_filename}"

            # Atomic write
            temp_path = self.temp_dir / f"tmp_{new_uuid()}_{storage_filename}"
            with open(temp_path, "wb") as f:
                f.write(file_bytes)
            shutil.move(str(temp_path), str(final_path))

            source_file = SourceFile(
                id=file_id,
                content_sha256=sha256,
                original_name=original_name,
                media_type=media_type,
                storage_key=storage_key,
                byte_size=byte_size,
                created_at=utc_now_iso()
            )

            conn.execute(
                """INSERT INTO source_files (id, content_sha256, original_name, media_type, storage_key, byte_size, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (source_file.id, source_file.content_sha256, source_file.original_name,
                 source_file.media_type, source_file.storage_key, source_file.byte_size,
                 source_file.created_at)
            )
            if managed_conn:
                conn.commit()

            return source_file
        finally:
            if managed_conn:
                conn.close()

    def get_source_file_path(self, storage_key: str) -> Optional[Path]:
        path = self.sources_dir / storage_key
        return path if path.exists() else None

    def get_source_file_by_id(self, source_file_id: str) -> Optional[SourceFile]:
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT id, content_sha256, original_name, media_type, storage_key, byte_size, created_at FROM source_files WHERE id = ?",
                (source_file_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return SourceFile(**dict(row))

    def cleanup_orphan_sources(self) -> int:
        """Deletes source files that are not referenced in pages table."""
        deleted_count = 0
        with self.get_connection() as conn:
            cur = conn.execute("""
                SELECT id, storage_key FROM source_files
                WHERE id NOT IN (SELECT DISTINCT source_file_id FROM pages)
            """)
            orphans = cur.fetchall()
            for row in orphans:
                file_id = row["id"]
                storage_key = row["storage_key"]
                path = self.sources_dir / storage_key
                if path.exists():
                    try:
                        path.unlink()
                    except Exception:
                        pass
                conn.execute("DELETE FROM source_files WHERE id = ?", (file_id,))
                deleted_count += 1
            conn.commit()
        return deleted_count

    # -------------------------------------------------------------------------
    # Documents CRUD
    # -------------------------------------------------------------------------
    def create_document(self, doc: Document) -> Document:
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO documents (
                    id, title, company, division, role, collection, author,
                    recruitment_year, outcome, grouping_status, completeness,
                    notes, deleted_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc.id, doc.title, doc.company, doc.division, doc.role,
                 doc.collection, doc.author, doc.recruitment_year, doc.outcome,
                 doc.grouping_status, doc.completeness, doc.notes,
                 doc.deleted_at, doc.created_at, doc.updated_at)
            )
            conn.commit()
        return doc

    def get_document(self, document_id: str, include_deleted: bool = False) -> Optional[Document]:
        with self.get_connection() as conn:
            query = "SELECT * FROM documents WHERE id = ?"
            if not include_deleted:
                query += " AND deleted_at IS NULL"
            cur = conn.execute(query, (document_id,))
            row = cur.fetchone()
            if not row:
                return None
            return Document(**dict(row))

    def list_documents(
        self,
        collection: Optional[str] = None,
        company: Optional[str] = None,
        role: Optional[str] = None,
        include_deleted: bool = False
    ) -> List[Document]:
        with self.get_connection() as conn:
            clauses = []
            params: List[Any] = []
            if not include_deleted:
                clauses.append("deleted_at IS NULL")
            if collection:
                clauses.append("collection = ?")
                params.append(collection)
            if company:
                clauses.append("company = ?")
                params.append(company)
            if role:
                clauses.append("role = ?")
                params.append(role)

            where_stmt = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            query = f"SELECT * FROM documents {where_stmt} ORDER BY created_at DESC"
            cur = conn.execute(query, params)
            return [Document(**dict(row)) for row in cur.fetchall()]

    def update_document(self, doc: Document) -> Document:
        doc.updated_at = utc_now_iso()
        with self.get_connection() as conn:
            conn.execute(
                """UPDATE documents SET
                    title = ?, company = ?, division = ?, role = ?,
                    collection = ?, author = ?, recruitment_year = ?,
                    outcome = ?, grouping_status = ?, completeness = ?,
                    notes = ?, updated_at = ?
                   WHERE id = ?""",
                (doc.title, doc.company, doc.division, doc.role,
                 doc.collection, doc.author, doc.recruitment_year,
                 doc.outcome, doc.grouping_status, doc.completeness,
                 doc.notes, doc.updated_at, doc.id)
            )
            conn.commit()
        return doc

    def delete_document(self, document_id: str) -> bool:
        """Soft-delete via tombstone (deleted_at) and remove from search index."""
        now = utc_now_iso()
        with self.get_connection() as conn:
            conn.execute("UPDATE documents SET deleted_at = ? WHERE id = ?", (now, document_id))
            # Remove from FTS and chunks
            conn.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document_id,))
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            conn.commit()

        try:
            self.sync_document_folder(document_id)
        except Exception:
            pass

        return True

    # -------------------------------------------------------------------------
    # Answers & Answer Revisions
    # -------------------------------------------------------------------------
    def create_answer(
        self,
        document_id: str,
        question_number: int,
        question_text: str,
        body_text: str,
        origin: str = "manual",
        review_status: str = "needs_user_review",
        answer_id: Optional[str] = None
    ) -> Tuple[Answer, AnswerRevision]:
        ans_id = answer_id or new_uuid()
        rev_id = new_uuid()
        sha = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
        now = utc_now_iso()

        ans = Answer(
            id=ans_id,
            document_id=document_id,
            question_number=question_number,
            current_revision_id=rev_id,
            created_at=now
        )
        rev = AnswerRevision(
            id=rev_id,
            answer_id=ans_id,
            parent_revision_id=None,
            question_text=question_text,
            body_text=body_text,
            text_sha256=sha,
            origin=origin,
            review_status=review_status,
            created_at=now
        )

        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO answers (id, document_id, question_number, current_revision_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (ans.id, ans.document_id, ans.question_number, ans.current_revision_id, ans.created_at)
            )
            conn.execute(
                """INSERT INTO answer_revisions (
                    id, answer_id, parent_revision_id, question_text,
                    body_text, text_sha256, origin, review_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (rev.id, rev.answer_id, rev.parent_revision_id, rev.question_text,
                 rev.body_text, rev.text_sha256, rev.origin, rev.review_status, rev.created_at)
            )
            conn.commit()

        return ans, rev

    def add_revision(
        self,
        answer_id: str,
        parent_revision_id: Optional[str],
        question_text: str,
        body_text: str,
        origin: str = "manual",
        review_status: str = "needs_user_review",
        set_as_current: bool = True
    ) -> AnswerRevision:
        rev_id = new_uuid()
        sha = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
        now = utc_now_iso()

        rev = AnswerRevision(
            id=rev_id,
            answer_id=answer_id,
            parent_revision_id=parent_revision_id,
            question_text=question_text,
            body_text=body_text,
            text_sha256=sha,
            origin=origin,
            review_status=review_status,
            created_at=now
        )

        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO answer_revisions (
                    id, answer_id, parent_revision_id, question_text,
                    body_text, text_sha256, origin, review_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (rev.id, rev.answer_id, rev.parent_revision_id, rev.question_text,
                 rev.body_text, rev.text_sha256, rev.origin, rev.review_status, rev.created_at)
            )
            if set_as_current:
                conn.execute(
                    "UPDATE answers SET current_revision_id = ? WHERE id = ?",
                    (rev.id, answer_id)
                )
            conn.commit()

        return rev

    def set_current_revision(self, answer_id: str, revision_id: str):
        with self.get_connection() as conn:
            conn.execute("UPDATE answers SET current_revision_id = ? WHERE id = ?", (revision_id, answer_id))
            conn.commit()

    def get_answer(self, answer_id: str) -> Optional[Answer]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM answers WHERE id = ?", (answer_id,))
            row = cur.fetchone()
            return Answer(**dict(row)) if row else None

    def get_answers_for_document(self, document_id: str) -> List[Tuple[Answer, Optional[AnswerRevision]]]:
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM answers WHERE document_id = ? ORDER BY question_number ASC",
                (document_id,)
            )
            results = []
            for a_row in cur.fetchall():
                ans = Answer(**dict(a_row))
                rev = None
                if ans.current_revision_id:
                    r_cur = conn.execute(
                        "SELECT * FROM answer_revisions WHERE id = ?",
                        (ans.current_revision_id,)
                    )
                    r_row = r_cur.fetchone()
                    if r_row:
                        rev = AnswerRevision(**dict(r_row))
                results.append((ans, rev))
            return results

    def get_revision(self, revision_id: str) -> Optional[AnswerRevision]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM answer_revisions WHERE id = ?", (revision_id,))
            row = cur.fetchone()
            return AnswerRevision(**dict(row)) if row else None

    def list_revisions(self, answer_id: str) -> List[AnswerRevision]:
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM answer_revisions WHERE answer_id = ? ORDER BY created_at ASC",
                (answer_id,)
            )
            return [AnswerRevision(**dict(row)) for row in cur.fetchall()]

    def set_revision_status(self, revision_id: str, status: str):
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE answer_revisions SET review_status = ? WHERE id = ?",
                (status, revision_id)
            )
            conn.commit()

    # -------------------------------------------------------------------------
    # Source Spans
    # -------------------------------------------------------------------------
    def add_source_spans(self, spans: List[SourceSpan]):
        with self.get_connection() as conn:
            for s in spans:
                bbox_json = json.dumps(s.bbox) if s.bbox is not None else None
                conn.execute(
                    """INSERT INTO source_spans (
                        id, revision_id, start_char, end_char, page_id,
                        source_id, bbox_json, uncertain, note
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (s.id, s.revision_id, s.start_char, s.end_char, s.page_id,
                     s.source_id, bbox_json, 1 if s.uncertain else 0, s.note)
                )
            conn.commit()

    def get_source_spans(self, revision_id: str) -> List[SourceSpan]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM source_spans WHERE revision_id = ?", (revision_id,))
            spans = []
            for row in cur.fetchall():
                bbox = json.loads(row["bbox_json"]) if row["bbox_json"] else None
                spans.append(SourceSpan(
                    id=row["id"],
                    revision_id=row["revision_id"],
                    start_char=row["start_char"],
                    end_char=row["end_char"],
                    page_id=row["page_id"],
                    source_id=row["source_id"],
                    bbox=bbox,
                    uncertain=bool(row["uncertain"]),
                    note=row["note"]
                ))
            return spans

    # -------------------------------------------------------------------------
    # Tag Management
    # -------------------------------------------------------------------------
    def ensure_tag(self, facet: str, label: str) -> Tag:
        canonical_id = f"{facet}:{label.strip()}"
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO tags (canonical_id, facet, label) VALUES (?, ?, ?)",
                (canonical_id, facet, label.strip())
            )
            conn.commit()
        return Tag(canonical_id=canonical_id, facet=facet, label=label.strip())

    def assign_tag(
        self,
        target_id: str,
        target_type: str,
        tag_id: str,
        origin: str = "manual",
        status: str = "suggested",
        evidence_quote: Optional[str] = None
    ) -> TagAssignment:
        assignment_id = new_uuid()
        now = utc_now_iso()
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO tag_assignments (id, target_id, target_type, tag_id, origin, status, evidence_quote, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(target_id, tag_id) DO UPDATE SET
                       origin = excluded.origin,
                       status = excluded.status,
                       evidence_quote = excluded.evidence_quote""",
                (assignment_id, target_id, target_type, tag_id, origin, status, evidence_quote, now)
            )
            conn.commit()
        return TagAssignment(
            id=assignment_id,
            target_id=target_id,
            target_type=target_type,
            tag_id=tag_id,
            origin=origin,
            status=status,
            evidence_quote=evidence_quote,
            created_at=now
        )

    def set_tag_status(self, target_id: str, tag_id: str, status: str):
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE tag_assignments SET status = ? WHERE target_id = ? AND tag_id = ?",
                (status, target_id, tag_id)
            )
            conn.commit()

    def get_tags_for_target(self, target_id: str) -> List[Tuple[Tag, TagAssignment]]:
        with self.get_connection() as conn:
            cur = conn.execute("""
                SELECT t.canonical_id, t.facet, t.label,
                       a.id as assignment_id, a.target_id, a.target_type, a.origin, a.status, a.evidence_quote, a.created_at
                FROM tags t
                JOIN tag_assignments a ON t.canonical_id = a.tag_id
                WHERE a.target_id = ?
            """, (target_id,))
            res = []
            for row in cur.fetchall():
                t = Tag(canonical_id=row["canonical_id"], facet=row["facet"], label=row["label"])
                a = TagAssignment(
                    id=row["assignment_id"],
                    target_id=row["target_id"],
                    target_type=row["target_type"],
                    tag_id=row["canonical_id"],
                    origin=row["origin"],
                    status=row["status"],
                    evidence_quote=row["evidence_quote"],
                    created_at=row["created_at"]
                )
                res.append((t, a))
            return res

    # -------------------------------------------------------------------------
    # Jobs Management
    # -------------------------------------------------------------------------
    def create_job(self, kind: str, target_id: str, input_hash: str, config_hash: str) -> Job:
        job = Job(
            id=new_uuid(),
            kind=kind,
            target_id=target_id,
            input_hash=input_hash,
            config_hash=config_hash,
            status="queued",
            attempt=0,
            progress=0.0
        )
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO jobs (
                    id, kind, target_id, input_hash, config_hash, status,
                    attempt, lease_until, progress, error_code, error_message,
                    result_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (job.id, job.kind, job.target_id, job.input_hash, job.config_hash,
                 job.status, job.attempt, job.lease_until, job.progress,
                 job.error_code, job.error_message, job.result_json,
                 job.created_at, job.updated_at)
            )
            conn.commit()
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
            return Job(**dict(row)) if row else None

    def update_job_status(
        self,
        job_id: str,
        status: str,
        progress: Optional[float] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        result_json: Optional[str] = None
    ):
        now = utc_now_iso()
        with self.get_connection() as conn:
            cur = conn.execute("SELECT progress, error_code, error_message, result_json FROM jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
            if not row:
                return
            new_prog = progress if progress is not None else row["progress"]
            new_err_code = error_code if error_code is not None else row["error_code"]
            new_err_msg = error_message if error_message is not None else row["error_message"]
            new_res = result_json if result_json is not None else row["result_json"]

            conn.execute(
                """UPDATE jobs SET status = ?, progress = ?, error_code = ?,
                   error_message = ?, result_json = ?, updated_at = ? WHERE id = ?""",
                (status, new_prog, new_err_code, new_err_msg, new_res, now, job_id)
            )
            conn.commit()

    # -------------------------------------------------------------------------
    # Export Operations
    # -------------------------------------------------------------------------
    def export_document_markdown(self, document_id: str) -> str:
        doc = self.get_document(document_id, include_deleted=True)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        answers = self.get_answers_for_document(document_id)
        lines = [
            f"# {doc.title}",
            "",
            f"- **기업/본부/직무**: {doc.company} / {doc.division} / {doc.role}",
            f"- **자료구분**: {doc.collection}",
            f"- **문서 상태**: {doc.grouping_status} (완결성: {doc.completeness})",
        ]
        if doc.notes:
            lines.append(f"- **메모**: {doc.notes}")
        lines.append("")

        for ans, rev in answers:
            lines.append(f"## 문항 {ans.question_number}")
            if rev:
                lines.append(f"**질문**: {rev.question_text}")
                lines.append("")
                lines.append(rev.body_text)
                lines.append("")
                lines.append(f"*(검수 상태: {rev.review_status}, 작성 기원: {rev.origin})*")
            else:
                lines.append("*(전사된 내용 없음)*")
            lines.append("")

        return "\n".join(lines)

    def export_document_txt(self, document_id: str) -> str:
        doc = self.get_document(document_id, include_deleted=True)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        answers = self.get_answers_for_document(document_id)
        lines = [
            f"[{doc.title}]",
            f"회사: {doc.company} | 직무: {doc.role}",
            "=" * 50,
            ""
        ]
        for ans, rev in answers:
            lines.append(f"[문항 {ans.question_number}]")
            if rev:
                lines.append(f"Q: {rev.question_text}")
                lines.append("-" * 30)
                lines.append(rev.body_text)
            else:
                lines.append("(내용 없음)")
            lines.append("\n")
        return "\n".join(lines)

    def export_document_zip(self, document_id: str) -> Path:
        doc = self.get_document(document_id, include_deleted=True)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        zip_filename = f"export_{doc.id}.zip"
        zip_path = self.exports_dir / zip_filename

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            md_content = self.export_document_markdown(document_id)
            txt_content = self.export_document_txt(document_id)
            zf.writestr(f"{doc.id}.md", md_content)
            zf.writestr(f"{doc.id}.txt", txt_content)

            manifest = {
                "document": doc.to_dict(),
                "exported_at": utc_now_iso(),
                "schema_version": self.CURRENT_SCHEMA_VERSION
            }
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        return zip_path

    # -------------------------------------------------------------------------
    # Document-Centric Folder Synchronization
    # -------------------------------------------------------------------------
    def get_document_folder_name(self, doc: Document) -> str:
        safe_company = re.sub(r'[\\/*?:"<>|]', "", doc.company or "기타").strip().replace(" ", "_")
        safe_title = re.sub(r'[\\/*?:"<>|]', "", doc.title or "자소서").strip().replace(" ", "_")
        return f"[{safe_company}]_{safe_title}_{doc.id[:8]}"

    def _generate_document_full_txt(self, doc: Document, answers: List[Tuple[Answer, Optional[AnswerRevision]]]) -> str:
        lines = [
            "=" * 80,
            f"[지원서] {doc.title}",
            f"[기업명] {doc.company}  |  [본부/사업부] {doc.division}  |  [지원직무] {doc.role}",
            f"[자료구분] {doc.collection}  |  [묶음상태] {doc.grouping_status} (완결성: {doc.completeness})",
        ]
        if doc.notes:
            lines.append(f"[메모] {doc.notes}")
        lines.append("=" * 80)
        lines.append("")

        for ans, rev in answers:
            lines.append(f"[문항 {ans.question_number}] {rev.question_text if rev else '(질문 미등록)'}")
            lines.append("-" * 80)
            if rev:
                lines.append(rev.body_text)
                lines.append("")
                no_spaces = len("".join(rev.body_text.split()))
                lines.append(f"(글자 수: {len(rev.body_text)}자 / 공백 제외 {no_spaces}자 | 검수 상태: {rev.review_status})")
            else:
                lines.append("(내용 없음)")
            lines.append("")
            lines.append("")

        return "\n".join(lines)

    def _generate_document_full_md(self, doc: Document, answers: List[Tuple[Answer, Optional[AnswerRevision]]]) -> str:
        lines = [
            f"# [{doc.company}] {doc.title}",
            "",
            f"> **지원 정보**: {doc.company} / {doc.division} / {doc.role}  ",
            f"> **자료 구분**: {doc.collection} | **문서 상태**: {doc.grouping_status} (완결성: {doc.completeness})  ",
        ]
        if doc.notes:
            lines.append(f"> **메모**: {doc.notes}  ")
        lines.append("")
        lines.append("---")
        lines.append("")

        for ans, rev in answers:
            lines.append(f"## 문항 {ans.question_number}. {rev.question_text if rev else '(질문 미등록)'}")
            lines.append("")
            if rev:
                lines.append(rev.body_text)
                lines.append("")
                no_spaces = len("".join(rev.body_text.split()))
                lines.append(f"- **분량**: {len(rev.body_text)}자 (공백 제외 {no_spaces}자)")
                lines.append(f"- **검수 상태**: `{rev.review_status}` | **작성 기원**: `{rev.origin}`")
            else:
                lines.append("*(내용 없음)*")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def sync_document_folder(self, document_id: str) -> Optional[Path]:
        """
        Synchronizes a document's full essay text files (.txt, .md, metadata.json)
        and associated original images into a dedicated document folder:
        documents/[Company]_[Title]_[ID]/
            ├── [Title].txt
            ├── [Title].md
            ├── metadata.json
            └── images/
                ├── 01_[original_name].jpeg
                └── ...
        """
        doc = self.get_document(document_id, include_deleted=True)
        if not doc:
            return None

        # Check for existing folder with this document prefix
        prefix = f"_{doc.id[:8]}"
        matched_dirs = [d for d in self.documents_dir.glob(f"*{prefix}") if d.is_dir()]

        if doc.deleted_at:
            for d in matched_dirs:
                if not d.name.startswith("_deleted_"):
                    deleted_name = f"_deleted_{d.name}"
                    d.rename(self.documents_dir / deleted_name)
            return None

        folder_name = self.get_document_folder_name(doc)
        doc_dir = self.documents_dir / folder_name

        # If an existing folder had a different name, rename it
        for d in matched_dirs:
            if d != doc_dir and not d.name.startswith("_deleted_"):
                try:
                    d.rename(doc_dir)
                    break
                except Exception:
                    pass

        doc_dir.mkdir(parents=True, exist_ok=True)
        images_dir = doc_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        # 1. Export Markdown and Text Content
        safe_title = re.sub(r'[\\/*?:"<>|]', "", doc.title or "자소서").strip().replace(" ", "_")
        txt_path = doc_dir / f"{safe_title}.txt"
        md_path = doc_dir / f"{safe_title}.md"
        meta_path = doc_dir / "metadata.json"

        answers = self.get_answers_for_document(document_id)
        txt_content = self._generate_document_full_txt(doc, answers)
        txt_path.write_text(txt_content, encoding="utf-8")

        md_content = self._generate_document_full_md(doc, answers)
        md_path.write_text(md_content, encoding="utf-8")

        # 2. Copy Original Images in Order
        with self.get_connection() as conn:
            cur = conn.execute("""
                SELECT dp.order_index, dp.page_kind, p.physical_page, s.storage_key, s.original_name
                FROM document_pages dp
                JOIN pages p ON dp.page_id = p.id
                JOIN source_files s ON p.source_file_id = s.id
                WHERE dp.document_id = ?
                ORDER BY dp.order_index ASC
            """, (doc.id,))
            pages_info = cur.fetchall()

        image_manifest = []
        for idx, p_row in enumerate(pages_info):
            s_key = p_row["storage_key"]
            orig_name = p_row["original_name"]
            page_kind = p_row["page_kind"]
            src_file_path = self.get_source_file_path(s_key)
            if src_file_path and src_file_path.exists():
                safe_orig_name = re.sub(r'[\\/*?:"<>|]', "", orig_name).strip()
                dest_img_name = f"{idx + 1:02d}_{safe_orig_name}"
                dest_img_path = images_dir / dest_img_name
                if not dest_img_path.exists() or dest_img_path.stat().st_size != src_file_path.stat().st_size:
                    shutil.copy2(src_file_path, dest_img_path)
                image_manifest.append({
                    "order": idx + 1,
                    "kind": page_kind,
                    "file": dest_img_name,
                    "original_name": orig_name
                })

        # 3. Write metadata.json
        manifest = {
            "id": doc.id,
            "title": doc.title,
            "company": doc.company,
            "division": doc.division,
            "role": doc.role,
            "collection": doc.collection,
            "author": doc.author,
            "recruitment_year": doc.recruitment_year,
            "outcome": doc.outcome,
            "grouping_status": doc.grouping_status,
            "completeness": doc.completeness,
            "notes": doc.notes,
            "total_answers": len(answers),
            "approved_answers": sum(1 for _, r in answers if r and r.review_status == "approved"),
            "images": image_manifest,
            "synced_at": utc_now_iso()
        }
        meta_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        return doc_dir

    def sync_all_document_folders(self) -> List[Path]:
        """Synchronizes all non-deleted documents into the documents/ folder."""
        docs = self.list_documents(include_deleted=False)
        synced_dirs = []
        for d in docs:
            p = self.sync_document_folder(d.id)
            if p:
                synced_dirs.append(p)
        return synced_dirs

    # -------------------------------------------------------------------------
    # Seed Data Import (Idempotent)
    # -------------------------------------------------------------------------
    def import_seed_data(self, seed_data: Dict[str, Any]) -> Dict[str, int]:
        """
        Imports seed.json safely and idempotently.
        Preserves 'needs_user_review' status and 'provisional' grouping.
        Does NOT duplicate entries if called repeatedly.
        """
        imported_docs = 0
        imported_answers = 0

        with self.get_connection() as conn:
            # 0. Sources & Pages
            source_map: Dict[str, Tuple[str, str]] = {}  # ext_s_id -> (src_id, page_id)
            for s in seed_data.get("sources", []):
                ext_s_id = s["id"]
                orig_name = s.get("original_filename", f"{ext_s_id}.jpeg")
                sha256 = s.get("sha256", "")
                rel_path = s.get("path", "")

                cur = conn.execute(
                    "SELECT internal_id FROM seed_imports WHERE external_id = ? AND entity_type = 'source'",
                    (ext_s_id,)
                )
                row = cur.fetchone()
                if row:
                    src_id = row["internal_id"]
                else:
                    cur2 = conn.execute(
                        "SELECT id FROM source_files WHERE content_sha256 = ?",
                        (sha256,)
                    )
                    row2 = cur2.fetchone()
                    if row2:
                        src_id = row2["id"]
                    else:
                        src_id = new_uuid()
                        possible_paths = [
                            base / rel_path
                            for base in (seed_handoff_dir(), PROJECT_ROOT, self.archive_root)
                            if base is not None
                        ]
                        found_path = None
                        for p in possible_paths:
                            if p.exists() and p.is_file():
                                found_path = p
                                break

                        prefix = (sha256[:2] if len(sha256) >= 2 else "xx")
                        dest_dir = self.sources_dir / prefix
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        ext = Path(orig_name).suffix.lower() or ".jpeg"
                        storage_filename = f"{sha256}{ext}"
                        final_path = dest_dir / storage_filename
                        storage_key = f"{prefix}/{storage_filename}"

                        if found_path:
                            file_data = found_path.read_bytes()
                            byte_sz = len(file_data)
                            shutil.copy2(str(found_path), str(final_path))
                        else:
                            file_data = b"placeholder"
                            byte_sz = len(file_data)
                            final_path.write_bytes(file_data)

                        conn.execute(
                            """INSERT OR IGNORE INTO source_files (id, content_sha256, original_name, media_type, storage_key, byte_size, created_at)
                               VALUES (?, ?, ?, 'image/jpeg', ?, ?, ?)""",
                            (src_id, sha256, orig_name, storage_key, byte_sz, utc_now_iso())
                        )

                    conn.execute(
                        "INSERT OR IGNORE INTO seed_imports (external_id, entity_type, internal_id, imported_at) VALUES (?, 'source', ?, ?)",
                        (ext_s_id, src_id, utc_now_iso())
                    )

                # Page record for source
                cur_p = conn.execute(
                    "SELECT id FROM pages WHERE source_file_id = ? AND physical_page = 1",
                    (src_id,)
                )
                p_row = cur_p.fetchone()
                if p_row:
                    page_id = p_row["id"]
                else:
                    page_id = new_uuid()
                    conn.execute(
                        """INSERT INTO pages (id, source_file_id, physical_page, orientation, preprocessing_version, created_at)
                           VALUES (?, ?, 1, 0, 1, ?)""",
                        (page_id, src_id, utc_now_iso())
                    )
                    conn.execute(
                        "INSERT OR IGNORE INTO seed_imports (external_id, entity_type, internal_id, imported_at) VALUES (?, 'page', ?, ?)",
                        (ext_s_id, page_id, utc_now_iso())
                    )
                source_map[ext_s_id] = (src_id, page_id)

            # 1. Documents
            for d in seed_data.get("documents", []):
                ext_id = d["id"]
                cur = conn.execute(
                    "SELECT internal_id FROM seed_imports WHERE external_id = ? AND entity_type = 'document'",
                    (ext_id,)
                )
                row = cur.fetchone()
                if row:
                    doc_id = row["internal_id"]
                else:
                    doc_id = new_uuid()
                    doc = Document(
                        id=doc_id,
                        title=d.get("title", ""),
                        company=d.get("company", ""),
                        division=d.get("division", ""),
                        role=d.get("role", ""),
                        collection=d.get("collection", "reference"),
                        author=d.get("author"),
                        recruitment_year=d.get("recruitment_year"),
                        outcome=d.get("outcome", "unknown"),
                        grouping_status=d.get("grouping_status", "provisional"),
                        completeness=d.get("completeness", "unknown"),
                        notes=d.get("notes"),
                        created_at=utc_now_iso(),
                        updated_at=utc_now_iso()
                    )
                    conn.execute(
                        """INSERT INTO documents (
                            id, title, company, division, role, collection, author,
                            recruitment_year, outcome, grouping_status, completeness,
                            notes, deleted_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (doc.id, doc.title, doc.company, doc.division, doc.role,
                         doc.collection, doc.author, doc.recruitment_year, doc.outcome,
                         doc.grouping_status, doc.completeness, doc.notes,
                         doc.deleted_at, doc.created_at, doc.updated_at)
                    )
                    conn.execute(
                        "INSERT INTO seed_imports (external_id, entity_type, internal_id, imported_at) VALUES (?, ?, ?, ?)",
                        (ext_id, "document", doc.id, utc_now_iso())
                    )
                    imported_docs += 1

                # Link document pages
                for ord_idx, s_id in enumerate(d.get("source_ids", [])):
                    if s_id in source_map:
                        _, p_id = source_map[s_id]
                        p_kind = "cover" if any(c.get("source_id") == s_id for c in seed_data.get("covers", [])) else "answer"
                        conn.execute(
                            """INSERT OR IGNORE INTO document_pages (document_id, page_id, order_index, page_kind)
                               VALUES (?, ?, ?, ?)""",
                            (doc_id, p_id, ord_idx, p_kind)
                        )

                # Tags for document
                for t in d.get("tags", []):
                    facet = t.get("facet", "general")
                    val = t.get("value", "")
                    status = t.get("status", "suggested")
                    canonical_id = f"{facet}:{val.strip()}"
                    conn.execute(
                        "INSERT OR IGNORE INTO tags (canonical_id, facet, label) VALUES (?, ?, ?)",
                        (canonical_id, facet, val.strip())
                    )
                    assign_id = new_uuid()
                    conn.execute(
                        """INSERT OR IGNORE INTO tag_assignments (id, target_id, target_type, tag_id, origin, status, evidence_quote, created_at)
                           VALUES (?, ?, 'document', ?, 'manual', ?, NULL, ?)""",
                        (assign_id, doc_id, canonical_id, status, utc_now_iso())
                    )

            # 2. Answers
            for a in seed_data.get("answers", []):
                ext_a_id = a["id"]
                cur = conn.execute(
                    "SELECT internal_id FROM seed_imports WHERE external_id = ? AND entity_type = 'answer'",
                    (ext_a_id,)
                )
                row = cur.fetchone()
                if row:
                    ans_id = row["internal_id"]
                else:
                    ext_doc_id = a["document_id"]
                    doc_cur = conn.execute(
                        "SELECT internal_id FROM seed_imports WHERE external_id = ? AND entity_type = 'document'",
                        (ext_doc_id,)
                    )
                    d_row = doc_cur.fetchone()
                    if not d_row:
                        continue
                    internal_doc_id = d_row["internal_id"]

                    ans_id = new_uuid()
                    rev_id = new_uuid()
                    q_num = a.get("question_number", 1)
                    q_text = a.get("question", "")
                    b_text = a.get("text", "")
                    sha = hashlib.sha256(b_text.encode("utf-8")).hexdigest()
                    now = utc_now_iso()

                    review_status = a.get("review_status", "needs_user_review")

                    conn.execute(
                        "INSERT INTO answers (id, document_id, question_number, current_revision_id, created_at) VALUES (?, ?, ?, ?, ?)",
                        (ans_id, internal_doc_id, q_num, rev_id, now)
                    )
                    conn.execute(
                        """INSERT INTO answer_revisions (
                            id, answer_id, parent_revision_id, question_text,
                            body_text, text_sha256, origin, review_status, created_at
                        ) VALUES (?, ?, NULL, ?, ?, ?, 'manual', ?, ?)""",
                        (rev_id, ans_id, q_text, b_text, sha, review_status, now)
                    )
                    conn.execute(
                        "INSERT INTO seed_imports (external_id, entity_type, internal_id, imported_at) VALUES (?, ?, ?, ?)",
                        (ext_a_id, "answer", ans_id, now)
                    )
                    imported_answers += 1

                    # Source spans
                    src_ref = a.get("source_id")
                    p_ref = source_map[src_ref][1] if src_ref in source_map else None
                    if src_ref:
                        span_id = new_uuid()
                        conn.execute(
                            """INSERT INTO source_spans (id, revision_id, start_char, end_char, page_id, source_id, bbox_json, uncertain, note)
                               VALUES (?, ?, 0, ?, ?, ?, NULL, 0, NULL)""",
                            (span_id, rev_id, len(b_text), p_ref, src_ref)
                        )

                # Answer tag assignments (import all tags with evidence_quote)
                for t in a.get("tag_assignments", []):
                    facet = t.get("facet", "general")
                    val = t.get("value", "").strip()
                    status = t.get("status", "suggested")
                    origin = t.get("origin", "assistant")
                    evidence_quote = t.get("evidence_quote")
                    canonical_id = f"{facet}:{val}"
                    conn.execute(
                        "INSERT OR IGNORE INTO tags (canonical_id, facet, label) VALUES (?, ?, ?)",
                        (canonical_id, facet, val)
                    )
                    assign_id = new_uuid()
                    conn.execute(
                        """INSERT OR IGNORE INTO tag_assignments (id, target_id, target_type, tag_id, origin, status, evidence_quote, created_at)
                           VALUES (?, ?, 'answer', ?, ?, ?, ?, ?)""",
                        (assign_id, ans_id, canonical_id, origin, status, evidence_quote, utc_now_iso())
                    )

            conn.commit()

        return {"documents": imported_docs, "answers": imported_answers}
