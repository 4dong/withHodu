"""
Automated test suite asserting correct behavior for all 19 audit findings (A01~A19).
Each test function tests that the defect is resolved and cannot regress.
"""

import os
import sys
import io
import json
import tempfile
import time
import subprocess
from pathlib import Path
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.essay.models import Document, new_uuid
from tests.essay.seed_fixtures import load_seed_json
from core.essay.repository import EssayRepository
from core.essay.ingest import EssayIngestService, IngestValidationError
from core.essay.style import EssayStyleService, StyleValidator
from core.essay.embedding import MockEmbeddingProvider
from core.essay.retrieval import EssaySearchEngine
from core.essay.rag import EssayRAGService, Citation, GroundedAnswer
from core.essay.jobs import JobManager
from core.essay.transcription import MockOCRProvider, OCRTranscriptionResult, GeminiVisionOCRProvider


def make_png(color: str) -> bytes:
    b = io.BytesIO()
    Image.new('RGB', (30, 30), color).save(b, format='PNG')
    return b.getvalue()


def test_a12_distinct_batch_upload_no_lock():
    """A12: Uploading distinct PNG images must not trigger 'database is locked' and must complete cleanly."""
    with tempfile.TemporaryDirectory(prefix='test-a12-') as tmp:
        repo = EssayRepository(tmp)
        ingest = EssayIngestService(repo)
        files = [
            ('red.png', make_png('red'), 'image/png'),
            ('blue.png', make_png('blue'), 'image/png'),
            ('green.png', make_png('green'), 'image/png')
        ]
        start = time.monotonic()
        doc, sources, pages = ingest.ingest_files(files, '다중사진 문서', '테스트기업', '개발본부', 'SW개발')
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"Batch upload took too long ({elapsed}s), possible lock contention"
        assert len(sources) == 3
        assert len(pages) == 3


def test_a13_reupload_same_image_foreign_key():
    """A13: Re-uploading the same image must reuse source and page without FOREIGN KEY constraint failure."""
    with tempfile.TemporaryDirectory(prefix='test-a13-') as tmp:
        repo = EssayRepository(tmp)
        ingest = EssayIngestService(repo)
        files = [('photo.png', make_png('yellow'), 'image/png')]

        doc1, sources1, pages1 = ingest.ingest_files(files, '문서1', '기업A', '본부A', '직무A')
        assert len(sources1) == 1
        assert len(pages1) == 1

        # Re-upload same image to a different document
        doc2, sources2, pages2 = ingest.ingest_files(files, '문서2', '기업B', '본부B', '직무B')
        assert len(sources2) == 1
        assert sources2[0].id == sources1[0].id
        assert len(pages2) == 1
        assert pages2[0].id == pages1[0].id


def test_a14_text_ingest_creates_answer():
    """A14: Text file ingestion must create an editable answer and revision."""
    with tempfile.TemporaryDirectory(prefix='test-a14-') as tmp:
        repo = EssayRepository(tmp)
        ingest = EssayIngestService(repo)
        doc, src = ingest.ingest_text_file(
            'my_essay.txt',
            '자율주행 알고리즘 개발 초안 본문입니다.',
            '자율주행 지원서',
            '현대차',
            'R&D',
            'SW'
        )
        answers = repo.get_answers_for_document(doc.id)
        assert len(answers) >= 1, "Text ingest must create at least one answer"
        ans, rev = answers[0]
        assert rev is not None
        assert '자율주행 알고리즘' in rev.body_text


def test_a15_invalid_pdf_rejected():
    """A15: Broken PDF bytes must be rejected by validate_file."""
    with tempfile.TemporaryDirectory(prefix='test-a15-') as tmp:
        repo = EssayRepository(tmp)
        ingest = EssayIngestService(repo)
        try:
            ingest.validate_file('fake.pdf', b'NOT A REAL PDF FILE', 'application/pdf')
            assert False, "Should raise IngestValidationError on invalid PDF bytes"
        except IngestValidationError:
            pass


def test_a16_job_idempotency():
    """A16: Enqueueing the same OCR task must return the existing job, not duplicate."""
    with tempfile.TemporaryDirectory(prefix='test-a16-') as tmp:
        repo = EssayRepository(tmp)
        ingest = EssayIngestService(repo)
        doc, sources, pages = ingest.ingest_files([('img.png', make_png('magenta'), 'image/png')], '문서', '회사', '본부', '직무')
        jm = JobManager(repo)
        job1 = jm.enqueue_ocr_job(doc.id, pages[0].id)
        job2 = jm.enqueue_ocr_job(doc.id, pages[0].id)
        assert job1.id == job2.id, f"Job enqueue must be idempotent: {job1.id} != {job2.id}"


def test_a17_cancelled_job_not_published():
    """A17: A cancelled job must not publish answers or mark status succeeded."""
    with tempfile.TemporaryDirectory(prefix='test-a17-') as tmp:
        repo = EssayRepository(tmp)
        ingest = EssayIngestService(repo)
        img_bytes = make_png('cyan')
        doc, sources, pages = ingest.ingest_files([('img.png', img_bytes, 'image/png')], '문서', '회사', '본부', '직무')
        jm = JobManager(repo)
        job = jm.enqueue_ocr_job(doc.id, pages[0].id)
        claimed = jm.claim_next_job()
        assert claimed is not None

        # Cancel job while running
        repo.update_job_status(claimed.id, 'cancelled')

        provider = MockOCRProvider(canned_responses={
            str(len(img_bytes)): OCRTranscriptionResult(
                page_kind='answer',
                question_number=1,
                question_text='질문',
                body_text='취소된 작업의 본문'
            )
        })
        jm.process_job(claimed, provider)

        final_job = repo.get_job(claimed.id)
        assert final_job.status == 'cancelled', f"Cancelled job was overwritten with status {final_job.status}"
        answers = repo.get_answers_for_document(doc.id)
        assert len(answers) == 0, "Cancelled job must not publish answers to the document"


def test_a18_cover_not_saved_as_answer():
    """A18: Pages identified as 'cover' must not be saved as answer bodies."""
    with tempfile.TemporaryDirectory(prefix='test-a18-') as tmp:
        repo = EssayRepository(tmp)
        ingest = EssayIngestService(repo)
        img_bytes = make_png('black')
        doc, sources, pages = ingest.ingest_files([('cover.png', img_bytes, 'image/png')], '표지문서', '회사', '본부', '직무')
        jm = JobManager(repo)
        job = jm.enqueue_ocr_job(doc.id, pages[0].id)
        claimed = jm.claim_next_job()
        provider = MockOCRProvider(canned_responses={
            str(len(img_bytes)): OCRTranscriptionResult(
                page_kind='cover',
                question_number=None,
                question_text='',
                body_text='2026 합격 비결 자기소개서 표지'
            )
        })
        jm.process_job(claimed, provider)

        answers = repo.get_answers_for_document(doc.id)
        assert len(answers) == 0, "Cover page must not create an Answer record"
        # Check notes or document metadata updated
        doc_updated = repo.get_document(doc.id)
        assert doc_updated.notes is not None and "표지" in doc_updated.notes


def test_a19_deterministic_mock_embedding_across_processes():
    """A19: MockEmbeddingProvider vectors must be identical across different PYTHONHASHSEED environments."""
    REPO = Path(__file__).resolve().parent.parent.parent
    code = (
        "import sys, hashlib; sys.path.insert(0, sys.argv[1]); "
        "from core.essay.embedding import MockEmbeddingProvider; "
        "print(hashlib.sha256(MockEmbeddingProvider().embed_query('안정적인 테스트 문장').tobytes()).hexdigest())"
    )
    r1 = subprocess.run([sys.executable, '-c', code, str(REPO)], capture_output=True, text=True, env={**os.environ, 'PYTHONHASHSEED': '100'})
    r2 = subprocess.run([sys.executable, '-c', code, str(REPO)], capture_output=True, text=True, env={**os.environ, 'PYTHONHASHSEED': '200'})
    assert r1.stdout.strip() == r2.stdout.strip(), "Mock embeddings must be deterministic and invariant to PYTHONHASHSEED"


def test_a02_fact_fabrication_rejected():
    """A02: Adding unmentioned achievements must fail validation and block acceptance."""
    val = StyleValidator.validate(
        input_text='회의록을 정리했습니다.',
        output_text='팀장으로 승진하여 국제 대회에서 우승했습니다.'
    )
    assert not val.can_accept, "Fabricated achievement facts must not be accepted"
    assert not val.valid


def test_a03_decimal_change_rejected():
    """A03: Changing numbers (e.g. 2.45mm to 2.99mm) must fail validation."""
    val = StyleValidator.validate(
        input_text='평균 오차는 2.45mm였습니다.',
        output_text='평균 오차는 2.99mm였습니다.'
    )
    assert not val.can_accept, "Changed decimal metric must be detected and rejected"
    assert not val.valid


def test_a04_over_limit_cannot_accept():
    """A04: Exceeding max_chars constraint must set can_accept=False."""
    val = StyleValidator.validate(
        input_text='보고서를 작성했습니다.',
        output_text='보고서를 작성했습니다. ' + ('추가 설명입니다. ' * 20),
        max_chars=30
    )
    assert val.length_satisfied is False
    assert val.can_accept is False, "Exceeding character limit must prevent acceptance"


def test_a05_unreviewed_excluded_from_search():
    """A05: Unreviewed revisions must NOT appear in default search."""
    with tempfile.TemporaryDirectory(prefix='test-a05-') as tmp:
        repo = EssayRepository(tmp)
        doc = repo.create_document(Document(id=new_uuid(), title='테스트', company='회사', division='본부', role='직무'))
        ans, rev = repo.create_answer(doc.id, 1, '질문', '센서 노이즈 분석 본문', review_status='needs_user_review')
        engine = EssaySearchEngine(repo, MockEmbeddingProvider())
        engine.index_revision(rev.id)

        # Default search must not return unreviewed revision
        res = engine.search('노이즈')
        assert len(res.hits) == 0, "Default search must exclude unreviewed revisions"


def test_a06_a07_a08_citation_rigorous_validation():
    """A06, A07, A08: Citation validation must strictly verify current revision, correct answer/doc parentage, and non-empty quote."""
    with tempfile.TemporaryDirectory(prefix='test-citations-') as tmp:
        repo = EssayRepository(tmp)
        doc1 = repo.create_document(Document(id=new_uuid(), title='문서1', company='회사1', division='본부', role='직무'))
        doc2 = repo.create_document(Document(id=new_uuid(), title='문서2', company='회사2', division='본부', role='직무'))
        ans1, rev1_v1 = repo.create_answer(doc1.id, 1, 'Q1', '버전1의 원본 본문 문장입니다.', review_status='approved')
        rev1_v2 = repo.add_revision(ans1.id, rev1_v1.id, 'Q1', '버전2의 원본 본문 문장입니다.', review_status='approved', set_as_current=True)

        ans2, rev2 = repo.create_answer(doc2.id, 1, 'Q2', '다른 문서의 본문입니다.', review_status='approved')

        engine = EssaySearchEngine(repo, MockEmbeddingProvider())
        rag = EssayRAGService(repo, engine)

        # A06: Citation targeting outdated revision rev1_v1 must be rejected
        cit_old = Citation('C1', ans1.id, rev1_v1.id, doc1.id, None, '버전1의 원본')
        assert len(rag._verify_citations([cit_old])) == 0, "Outdated revision citation must be rejected"

        # A07: Mismatched answer and revision (ans2 paired with rev1_v2) must be rejected
        cit_mismatched = Citation('C2', ans2.id, rev1_v2.id, doc2.id, None, '버전2의 원본')
        assert len(rag._verify_citations([cit_mismatched])) == 0, "Mismatched answer-revision pair must be rejected"

        # A08: Empty quote must be rejected
        cit_empty = Citation('C3', ans1.id, rev1_v2.id, doc1.id, None, '')
        assert len(rag._verify_citations([cit_empty])) == 0, "Empty quote citation must be rejected"


def test_a09_uncited_answer_downgraded():
    """A09: Answers with status 'answered' but 0 valid citations must be downgraded to 'insufficient_evidence'."""
    with tempfile.TemporaryDirectory(prefix='test-a09-') as tmp:
        repo = EssayRepository(tmp)
        engine = EssaySearchEngine(repo, MockEmbeddingProvider())
        class UncitedGenerator:
            def generate(self, *args):
                return GroundedAnswer(status='answered', answer='근거 없는 확정 답변입니다.', citations=[], limitations=[])
        rag = EssayRAGService(repo, engine, generator=UncitedGenerator())
        ans = rag.answer_question('어떤 경험이 있나요?')
        assert ans.status == 'insufficient_evidence', "Uncited answer must be downgraded to insufficient_evidence"


def test_a10_empty_ocr_rejected():
    """A10: Parsing empty OCR JSON `{}` must raise ValueError."""
    provider = GeminiVisionOCRProvider(api_key='synthetic-key')
    try:
        provider._parse_json_result('{}')
        assert False, "Should raise ValueError on empty OCR JSON"
    except ValueError:
        pass


def test_a11_seed_import_preserves_sources_and_all_tags():
    """A11: Seed import must preserve all source files, pages, and all 47 answer tags with evidence."""
    seed_data = load_seed_json("seed.json")
    with tempfile.TemporaryDirectory(prefix='test-a11-') as tmp:
        repo = EssayRepository(tmp)
        repo.import_seed_data(seed_data)
        with repo.get_connection() as conn:
            c_sources = conn.execute('SELECT COUNT(*) FROM source_files').fetchone()[0]
            c_pages = conn.execute('SELECT COUNT(*) FROM pages').fetchone()[0]
            c_tags = conn.execute('SELECT COUNT(*) FROM tag_assignments').fetchone()[0]

        assert c_sources == 6, f"Expected 6 sources from seed, got {c_sources}"
        assert c_pages == 6, f"Expected 6 pages from seed, got {c_pages}"
        assert c_tags >= 47, f"Expected at least 47 tag assignments, got {c_tags}"


if __name__ == '__main__':
    # Run all tests
    funcs = [v for k, v in list(globals().items()) if k.startswith('test_') and callable(v)]
    passed = 0
    failed = 0
    for f in funcs:
        try:
            f()
            print(f"PASS: {f.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL: {f.__name__} - {e}")
            failed += 1
    print(f"\nSummary: {passed} passed, {failed} failed")
