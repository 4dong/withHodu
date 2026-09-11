"""
Unit and Integration Tests for Ingest, OCR Providers, and Jobs (P2 Milestone)
"""

import os
import sys
import io
import tempfile
import shutil
from pathlib import Path
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.essay.repository import EssayRepository
from core.essay.ingest import EssayIngestService, IngestValidationError
from core.essay.transcription import MockOCRProvider, OCRTranscriptionResult, UncertainSpan
from core.essay.jobs import JobManager


def create_dummy_png(text_mark: str = "test") -> bytes:
    img = Image.new("RGB", (200, 100), color=(73, 109, 137))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_ingest_and_ocr_lifecycle():
    temp_dir = tempfile.mkdtemp()
    try:
        repo = EssayRepository(archive_root=temp_dir)
        ingest_svc = EssayIngestService(repo)

        # 1. Validation checks
        # Empty file
        try:
            ingest_svc.validate_file("empty.png", b"")
            assert False, "Should fail on empty file"
        except IngestValidationError:
            pass

        # Corrupt image
        try:
            ingest_svc.validate_file("corrupt.png", b"not a png at all")
            assert False, "Should fail on corrupt image"
        except IngestValidationError:
            pass

        # 2. Ingest batch of valid images
        img1 = create_dummy_png("q1")
        img2 = create_dummy_png("q2")
        files = [
            ("kia_q1.png", img1, "image/png"),
            ("kia_q2.png", img2, "image/png")
        ]

        doc, sources, pages = ingest_svc.ingest_files(
            files=files,
            document_title="기아 전장 SW 품질 지원서",
            company="기아",
            division="품질본부",
            role="SW 품질",
            collection="reference"
        )
        assert len(sources) == 2
        assert len(pages) == 2
        assert doc.grouping_status == "provisional"

        # 3. Direct text file ingest
        txt_doc, txt_src = ingest_svc.ingest_text_file(
            filename="my_draft.txt",
            text_content="본인의 자율주행 알고리즘 개발 초안입니다.",
            document_title="현대차 자율주행 초안",
            company="현대자동차",
            division="R&D본부",
            role="자율주행",
            collection="own_draft"
        )
        assert txt_doc.collection == "own_draft"
        assert txt_doc.grouping_status == "confirmed"

        # 4. Enqueue OCR jobs for the image pages
        mock_provider = MockOCRProvider(
            canned_responses={
                str(len(img1)): OCRTranscriptionResult(
                    page_kind="answer",
                    question_number=1,
                    question_text="PV5를 활용한 지원 동기",
                    body_text="PV5를 접하며 EV 플랫폼의 확장을 확인했습니다. CANalyzer로 검증했습니다.",
                    uncertain_spans=[
                        UncertainSpan(start_char=0, end_char=3, text="PV5", note="약어 확인 필요")
                    ]
                )
            }
        )

        job_mgr = JobManager(repo, ocr_provider=mock_provider)
        job1 = job_mgr.enqueue_ocr_job(doc.id, pages[0].id)
        assert job1.status == "queued"

        # Claim and process job
        claimed = job_mgr.claim_next_job()
        assert claimed is not None
        assert claimed.id == job1.id
        assert claimed.status == "running"

        success = job_mgr.process_job(claimed)
        assert success is True

        finished_job = repo.get_job(job1.id)
        assert finished_job.status == "succeeded"
        assert finished_job.progress == 1.0

        # Verify created answer and spans
        answers = repo.get_answers_for_document(doc.id)
        assert len(answers) == 1
        ans, rev = answers[0]
        assert ans.question_number == 1
        assert "PV5를 활용한 지원 동기" in rev.question_text
        assert "CANalyzer로 검증했습니다." in rev.body_text
        assert rev.review_status == "needs_user_review"

        spans = repo.get_source_spans(rev.id)
        assert len(spans) == 1
        assert spans[0].uncertain is True
        assert spans[0].note == "약어 확인 필요"

        # 5. Test transient error and retry
        failing_provider = MockOCRProvider(failure_mode="429")
        job2 = job_mgr.enqueue_ocr_job(doc.id, pages[1].id)
        claimed2 = job_mgr.claim_next_job()
        assert claimed2 is not None

        fail_res = job_mgr.process_job(claimed2, ocr_provider=failing_provider)
        assert fail_res is False
        retrying_job = repo.get_job(job2.id)
        # Attempt 1 -> transient error, re-queued for retry
        assert retrying_job.status == "queued"
        assert retrying_job.attempt == 1
        assert retrying_job.error_code == "TRANSIENT_ERROR"

        print("✅ Ingest, OCR Providers, and JobManager tests passed.")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_ingest_and_ocr_lifecycle()
