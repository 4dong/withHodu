"""
File ingestion, validation, and batch document grouping for Essay Archive.
"""

from __future__ import annotations
import io
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image

from core.essay.models import (
    Document, SourceFile, Page, DocumentPage, new_uuid, utc_now_iso
)
from core.essay.repository import EssayRepository

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_BATCH_PAGES = 100
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_TEXT_EXTS = {".txt", ".md", ".markdown"}


class IngestValidationError(Exception):
    pass


class EssayIngestService:
    def __init__(self, repository: EssayRepository):
        self.repo = repository

    def validate_file(self, filename: str, file_bytes: bytes, mime_type: Optional[str] = None) -> str:
        """Validates file size, integrity, and determined media type."""
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise IngestValidationError(f"파일 '{filename}' 크기({len(file_bytes)} bytes)가 최대 한도(50MB)를 초과했습니다.")
        if len(file_bytes) == 0:
            raise IngestValidationError(f"파일 '{filename}'이 비어 있습니다.")

        ext = Path(filename).suffix.lower()
        determined_mime = mime_type or ""

        if ext in [".jpg", ".jpeg"]:
            determined_mime = "image/jpeg"
        elif ext == ".png":
            determined_mime = "image/png"
        elif ext == ".webp":
            determined_mime = "image/webp"
        elif ext == ".pdf":
            determined_mime = "application/pdf"
        elif ext in ALLOWED_TEXT_EXTS:
            determined_mime = "text/plain"

        if determined_mime == "application/pdf" or ext == ".pdf":
            if not file_bytes.startswith(b"%PDF-"):
                raise IngestValidationError(f"유효하지 않은 PDF 파일 형식입니다 ({filename}).")

        # Verify images with Pillow
        if determined_mime in ALLOWED_IMAGE_MIMES:
            try:
                img = Image.open(io.BytesIO(file_bytes))
                img.verify()
            except Exception as e:
                raise IngestValidationError(f"유효하지 않은 이미지 파일입니다 ({filename}): {e}")

        return determined_mime

    def ingest_files(
        self,
        files: List[Tuple[str, bytes, Optional[str]]],
        document_title: str,
        company: str,
        division: str,
        role: str,
        collection: str = "reference"
    ) -> Tuple[Document, List[SourceFile], List[Page]]:
        """
        Ingests a batch of files for a single document.
        Files: list of (original_name, file_bytes, mime_type)
        """
        if len(files) > MAX_BATCH_PAGES:
            raise IngestValidationError(f"일괄 추가 페이지 수({len(files)})가 한도({MAX_BATCH_PAGES})를 초과했습니다.")

        now = utc_now_iso()
        doc = Document(
            id=new_uuid(),
            title=document_title,
            company=company,
            division=division,
            role=role,
            collection=collection,
            grouping_status="provisional",
            completeness="unknown",
            created_at=now,
            updated_at=now
        )
        self.repo.create_document(doc)

        stored_sources: List[SourceFile] = []
        pages: List[Page] = []

        with self.repo.get_connection() as conn:
            for idx, (fname, fbytes, mime) in enumerate(files):
                media_type = self.validate_file(fname, fbytes, mime)
                src = self.repo.store_source_file(fbytes, fname, media_type, conn=conn)
                stored_sources.append(src)

                # Query if page record already exists for this source and page
                cur = conn.execute(
                    "SELECT id, orientation, preprocessing_version, created_at FROM pages WHERE source_file_id = ? AND physical_page = ?",
                    (src.id, idx + 1)
                )
                row = cur.fetchone()
                if row:
                    actual_page_id = row["id"]
                    page = Page(
                        id=actual_page_id,
                        source_file_id=src.id,
                        physical_page=idx + 1,
                        orientation=row["orientation"],
                        preprocessing_version=row["preprocessing_version"],
                        created_at=row["created_at"]
                    )
                else:
                    actual_page_id = new_uuid()
                    page = Page(
                        id=actual_page_id,
                        source_file_id=src.id,
                        physical_page=idx + 1,
                        orientation=0,
                        preprocessing_version=1,
                        created_at=now
                    )
                    conn.execute(
                        """INSERT INTO pages (id, source_file_id, physical_page, orientation, preprocessing_version, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (page.id, page.source_file_id, page.physical_page, page.orientation, page.preprocessing_version, page.created_at)
                    )

                # Link page to document
                page_kind = "cover" if idx == 0 and "표지" in fname else "answer"
                conn.execute(
                    """INSERT OR IGNORE INTO document_pages (document_id, page_id, order_index, page_kind)
                       VALUES (?, ?, ?, ?)""",
                    (doc.id, actual_page_id, idx, page_kind)
                )
                pages.append(page)

            conn.commit()

        # Synchronize into dedicated document folder (txt + images)
        try:
            self.repo.sync_document_folder(doc.id)
        except Exception:
            pass

        return doc, stored_sources, pages

    def ingest_text_file(
        self,
        filename: str,
        text_content: str,
        document_title: str,
        company: str,
        division: str,
        role: str,
        collection: str = "own_draft"
    ) -> Tuple[Document, SourceFile]:
        """Direct ingestion of text/markdown without OCR."""
        text_bytes = text_content.encode("utf-8")
        media_type = "text/plain" if filename.endswith(".txt") else "text/markdown"
        self.validate_file(filename, text_bytes, media_type)
        src = self.repo.store_source_file(text_bytes, filename, media_type)

        now = utc_now_iso()
        doc = Document(
            id=new_uuid(),
            title=document_title,
            company=company,
            division=division,
            role=role,
            collection=collection,
            grouping_status="confirmed",
            completeness="complete",
            created_at=now,
            updated_at=now
        )
        self.repo.create_document(doc)

        # Create Answer & revision so it's editable immediately (A14)
        self.repo.create_answer(
            document_id=doc.id,
            question_number=1,
            question_text="",
            body_text=text_content,
            origin="manual",
            review_status="needs_user_review"
        )
        try:
            self.repo.sync_document_folder(doc.id)
        except Exception:
            pass
        return doc, src
