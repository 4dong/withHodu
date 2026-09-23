"""
Background Job Worker and Execution Manager for Essay Processing.
"""

from __future__ import annotations
import hashlib
import json
from typing import Optional
from datetime import datetime, timezone, timedelta

from core.essay.models import Job, SourceSpan, new_uuid, utc_now_iso
from core.essay.repository import EssayRepository
from core.essay.transcription import BaseOCRProvider


class JobExecutionError(Exception):
    pass


class JobManager:
    MAX_ATTEMPTS = 3

    def __init__(self, repository: EssayRepository, ocr_provider: Optional[BaseOCRProvider] = None):
        self.repo = repository
        self.ocr_provider = ocr_provider

    def enqueue_ocr_job(self, document_id: str, page_id: str, config_hash: str = "default_v1") -> Job:
        """Enqueues an OCR transcription job for a given page with idempotency."""
        target_id = f"{document_id}:{page_id}"
        input_hash = hashlib.sha256(target_id.encode("utf-8")).hexdigest()

        # Idempotency check: reuse existing job if queued, running, or succeeded (A16)
        with self.repo.get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM jobs WHERE kind = 'ocr' AND target_id = ? AND status IN ('queued', 'running', 'succeeded') ORDER BY created_at DESC LIMIT 1",
                (target_id,)
            )
            row = cur.fetchone()
            if row:
                return Job(**dict(row))

        job = self.repo.create_job(
            kind="ocr",
            target_id=target_id,
            input_hash=input_hash,
            config_hash=config_hash
        )
        return job

    def claim_next_job(self) -> Optional[Job]:
        """Atomically claims the next queued job."""
        now = utc_now_iso()
        lease = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

        with self.repo.get_connection() as conn:
            cur = conn.execute("""
                SELECT * FROM jobs
                WHERE status = 'queued' OR (status = 'running' AND lease_until < ?)
                ORDER BY created_at ASC LIMIT 1
            """, (now,))
            row = cur.fetchone()
            if not row:
                return None

            job_id = row["id"]
            conn.execute(
                "UPDATE jobs SET status = 'running', lease_until = ?, attempt = attempt + 1, updated_at = ? WHERE id = ?",
                (lease, now, job_id)
            )
            conn.commit()

            cur = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            return Job(**dict(cur.fetchone()))

    def process_job(self, job: Job, ocr_provider: Optional[BaseOCRProvider] = None) -> bool:
        provider = ocr_provider or self.ocr_provider
        if not provider:
            self.repo.update_job_status(
                job.id, status="failed",
                error_code="NO_PROVIDER",
                error_message="OCR 공급자가 지정되지 않았습니다."
            )
            return False

        if job.kind == "ocr":
            return self._process_ocr_job(job, provider)
        else:
            self.repo.update_job_status(
                job.id, status="failed",
                error_code="UNKNOWN_KIND",
                error_message=f"알 수 없는 작업 종류: {job.kind}"
            )
            return False

    def _process_ocr_job(self, job: Job, provider: BaseOCRProvider) -> bool:
        doc_id, page_id = job.target_id.split(":")
        doc = self.repo.get_document(doc_id)
        if not doc:
            self.repo.update_job_status(job.id, status="failed", error_code="DOC_NOT_FOUND", error_message="문서를 찾을 수 없습니다.")
            return False

        with self.repo.get_connection() as conn:
            cur = conn.execute("""
                SELECT p.id as page_id, p.physical_page, s.id as source_file_id, s.storage_key, s.media_type
                FROM pages p
                JOIN source_files s ON p.source_file_id = s.id
                WHERE p.id = ?
            """, (page_id,))
            row = cur.fetchone()
            if not row:
                self.repo.update_job_status(job.id, status="failed", error_code="PAGE_NOT_FOUND", error_message="페이지를 찾을 수 없습니다.")
                return False

            storage_key = row["storage_key"]
            media_type = row["media_type"]
            page_num = row["physical_page"]

        file_path = self.repo.get_source_file_path(storage_key)
        if not file_path or not file_path.exists():
            self.repo.update_job_status(job.id, status="failed", error_code="FILE_NOT_FOUND", error_message="원본 파일을 찾을 수 없습니다.")
            return False

        with open(file_path, "rb") as f:
            img_bytes = f.read()

        try:
            result = provider.transcribe(img_bytes, mime_type=media_type)

            # Check if job was cancelled while running (A17)
            current_job = self.repo.get_job(job.id)
            if current_job and current_job.status == "cancelled":
                return False

            if result.page_kind == "cover":
                # A18: Cover page must update document notes, not create Answer
                cover_note = f"[표지]: {result.body_text}".strip()
                existing_notes = doc.notes or ""
                updated_notes = f"{existing_notes}\n{cover_note}".strip() if existing_notes else cover_note
                doc.notes = updated_notes
                self.repo.update_document(doc)

                with self.repo.get_connection() as conn:
                    conn.execute(
                        "UPDATE document_pages SET page_kind = 'cover' WHERE document_id = ? AND page_id = ?",
                        (doc_id, page_id)
                    )
                    conn.commit()

                self.repo.update_job_status(
                    job.id,
                    status="succeeded",
                    progress=1.0,
                    result_json=json.dumps(result.to_dict(), ensure_ascii=False)
                )
                return True

            # Save transcription result as a new answer or update
            q_num = result.question_number or page_num

            # Resolve question_number collision defensively
            with self.repo.get_connection() as conn:
                cur = conn.execute(
                    "SELECT question_number FROM answers WHERE document_id = ?",
                    (doc_id,)
                )
                existing_q_nums = {r["question_number"] for r in cur.fetchall()}
                if q_num in existing_q_nums:
                    if page_num not in existing_q_nums:
                        q_num = page_num
                    else:
                        q_num = max(existing_q_nums) + 1

            q_text = result.question_text or f"문항 {q_num}"
            b_text = result.body_text

            ans, rev = self.repo.create_answer(
                document_id=doc_id,
                question_number=q_num,
                question_text=q_text,
                body_text=b_text,
                origin="ocr",
                review_status="needs_user_review"
            )

            # Save uncertain spans
            spans_to_add = []
            for u in result.uncertain_spans:
                spans_to_add.append(SourceSpan(
                    id=new_uuid(),
                    revision_id=rev.id,
                    start_char=u.start_char,
                    end_char=u.end_char,
                    page_id=page_id,
                    uncertain=True,
                    note=u.note
                ))
            if spans_to_add:
                self.repo.add_source_spans(spans_to_add)

            self.repo.update_job_status(
                job.id,
                status="succeeded",
                progress=1.0,
                result_json=json.dumps(result.to_dict(), ensure_ascii=False)
            )
            return True

        except Exception as e:
            err_msg = str(e)
            if job.attempt >= self.MAX_ATTEMPTS:
                self.repo.update_job_status(
                    job.id, status="failed",
                    progress=job.progress,
                    error_code="MAX_RETRIES_EXCEEDED",
                    error_message=f"최대 재시도 횟수 초과: {err_msg}"
                )
            else:
                self.repo.update_job_status(
                    job.id, status="queued",
                    progress=job.progress,
                    error_code="TRANSIENT_ERROR",
                    error_message=f"일시 오류로 재시도 대기: {err_msg}"
                )
            return False
