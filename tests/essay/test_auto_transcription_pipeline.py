"""
Unit tests verifying automated OCR transcription pipeline upon import and review queue synchronization.
"""

import tempfile
import io
from pathlib import Path
from PIL import Image

from core.essay.repository import EssayRepository
from core.essay.ingest import EssayIngestService
from core.essay.jobs import JobManager
from core.essay.transcription import MockOCRProvider, OCRTranscriptionResult, get_active_ocr_provider


def make_test_image(text: str = "Test") -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(200, 200, 200))
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_import_immediate_transcription_pipeline():
    """Verify that after ingesting files and enqueuing jobs, immediate worker claims and processes all jobs to create answers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = EssayRepository(tmpdir)
        ingest_svc = EssayIngestService(repo)

        # 1. Ingest 2 pages of images
        img1 = make_test_image("Page 1")
        img2 = make_test_image("Page 2")
        files = [
            ("photo_1.jpg", img1, "image/jpeg"),
            ("photo_2.jpg", img2, "image/jpeg")
        ]

        doc, sources, pages = ingest_svc.ingest_files(
            files=files,
            document_title="현대차 자소서",
            company="현대자동차",
            division="R&D",
            role="자율주행",
            collection="own_draft"
        )

        assert len(pages) == 2

        # 2. Enqueue jobs
        job_mgr = JobManager(repo)
        jobs = []
        for p in pages:
            j = job_mgr.enqueue_ocr_job(doc.id, p.id)
            jobs.append(j)

        assert len(jobs) == 2

        # 3. Process jobs with mock OCR provider
        mock_ocr = MockOCRProvider()
        success_cnt = 0
        for _ in jobs:
            claimed = job_mgr.claim_next_job()
            assert claimed is not None
            ok = job_mgr.process_job(claimed, ocr_provider=mock_ocr)
            assert ok is True
            success_cnt += 1

        assert success_cnt == 2

        # 4. Check that answers and revisions are created with needs_user_review
        answers = repo.get_answers_for_document(doc.id)
        assert len(answers) >= 1
        unreviewed = [(a, r) for a, r in answers if r and r.review_status == "needs_user_review"]
        assert len(unreviewed) >= 1

        print("✅ test_import_immediate_transcription_pipeline passed successfully.")


if __name__ == "__main__":
    test_import_immediate_transcription_pipeline()
