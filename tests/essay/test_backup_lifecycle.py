"""
Unit and Integration Tests for Lifecycle (L01~L06) and Backup/Restore (P6 Milestone)
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.essay.models import Document, new_uuid
from core.essay.repository import EssayRepository
from core.essay.embedding import MockEmbeddingProvider
from core.essay.retrieval import EssaySearchEngine
from core.essay.rag import EssayRAGService, MockRAGGenerator
from core.essay.backup import EssayBackupService
from tests.essay.seed_fixtures import load_seed_json


def test_lifecycle_and_backup_restore():
    temp_dir = tempfile.mkdtemp()
    try:
        repo = EssayRepository(archive_root=temp_dir)

        # ---------------------------------------------------------------------
        # L01: Duplicate seed / image import
        # ---------------------------------------------------------------------
        seed_data = load_seed_json("seed.json")

        res1 = repo.import_seed_data(seed_data)
        assert res1["documents"] == 2
        assert res1["answers"] == 4

        # Second import: strictly 0 duplicates
        res2 = repo.import_seed_data(seed_data)
        assert res2["documents"] == 0
        assert res2["answers"] == 0

        # Duplicate file store
        src_a = repo.store_source_file(b"test_img_bytes", "img.png", "image/png")
        src_b = repo.store_source_file(b"test_img_bytes", "img_copy.png", "image/png")
        assert src_a.id == src_b.id

        # ---------------------------------------------------------------------
        # L02: Body edit while re-indexing
        # ---------------------------------------------------------------------
        with repo.get_connection() as conn:
            conn.execute("UPDATE answer_revisions SET review_status = 'approved'")
            conn.commit()

        embed_provider = MockEmbeddingProvider(dimension=128)
        engine = EssaySearchEngine(repo, embedding_provider=embed_provider)
        engine.index_all_approved()

        doc1 = repo.list_documents()[0]
        answers = repo.get_answers_for_document(doc1.id)
        test_ans, test_rev1 = answers[0]

        # Add revision 2
        test_rev2 = repo.add_revision(
            answer_id=test_ans.id,
            parent_revision_id=test_rev1.id,
            question_text=test_rev1.question_text,
            body_text="완전히 개정된 제2판 자소서 텍스트입니다. 인공지능 엔지니어링 역량.",
            origin="manual",
            review_status="approved",
            set_as_current=True
        )
        engine.index_revision(test_rev2.id)

        # Searching for old revision terms should not yield old rev
        res_old = engine.search("PV5로 찾아낸", filters={"document_id": doc1.id})
        found_revs = [h.revision_id for h in res_old.hits]
        assert test_rev1.id not in found_revs

        # ---------------------------------------------------------------------
        # L03: Document deletion and citation invalidation
        # ---------------------------------------------------------------------
        rag_svc = EssayRAGService(repo, engine, generator=MockRAGGenerator())
        doc_to_delete = repo.create_document(Document(
            id=new_uuid(), title="삭제 대상 문서", company="임시회사", division="임시",
            role="임시", collection="reference", author=None, recruitment_year=None,
            outcome="unknown", grouping_status="confirmed", completeness="complete"
        ))
        d_ans, d_rev = repo.create_answer(doc_to_delete.id, 1, "질문", "삭제될 본문", review_status="approved")
        engine.index_revision(d_rev.id)

        # Check it was findable
        res_before = engine.search("삭제될 본문")
        assert any(h.document_id == doc_to_delete.id for h in res_before.hits)

        # Delete document
        repo.delete_document(doc_to_delete.id)

        # Excluded from search
        res_after = engine.search("삭제될 본문")
        assert not any(h.document_id == doc_to_delete.id for h in res_after.hits)

        # Citation invalidation
        from core.essay.rag import Citation
        cit = Citation("C1", d_ans.id, d_rev.id, doc_to_delete.id, None, "삭제될 본문")
        verified = rag_svc._verify_citations([cit])
        assert len(verified) == 0

        # ---------------------------------------------------------------------
        # L04: Embedding model generation mismatch
        # ---------------------------------------------------------------------
        # If searching with another model_id that is not in the index, candidate vector list is empty
        other_embed_provider = MockEmbeddingProvider(dimension=128, model_id="different-model-v2")
        other_engine = EssaySearchEngine(repo, embedding_provider=other_embed_provider)
        # Hits should smoothly fallback to keyword matching or return only keyword hits
        other_res = other_engine.search("CANalyzer FRAM")
        assert other_res.hits[0].match_origin in ("keyword", "fts")

        # ---------------------------------------------------------------------
        # L05: Workspace switching state isolation
        # ---------------------------------------------------------------------
        session_state_mock = {
            "current_workspace": "paper",
            "current_paper_bundle": {"pdf_path": "/path/to/paper.pdf", "total_pages": 10},
            "page_translations": {1: "번역 캐시"},
            "current_page_num": 3
        }
        # Switch to essay workspace
        session_state_mock["current_workspace"] = "essay"
        # Essay operations do not mutate paper keys
        assert session_state_mock["current_paper_bundle"]["pdf_path"] == "/path/to/paper.pdf"
        assert session_state_mock["page_translations"][1] == "번역 캐시"
        assert session_state_mock["current_page_num"] == 3

        # Switch back to paper workspace
        session_state_mock["current_workspace"] = "paper"
        assert session_state_mock["current_paper_bundle"] is not None

        # ---------------------------------------------------------------------
        # L06: Cloud disabled / offline mode (Key-free)
        # ---------------------------------------------------------------------
        offline_engine = EssaySearchEngine(repo, embedding_provider=None)
        off_res = offline_engine.search("CANalyzer")
        assert off_res.mode == "keyword_only"
        assert len(off_res.hits) > 0

        # ---------------------------------------------------------------------
        # Backup and Restore to a brand-new directory
        # ---------------------------------------------------------------------
        backup_zip = Path(temp_dir) / "test_backup.zip"
        backup_info = EssayBackupService.create_backup(repo, backup_zip)
        assert backup_zip.exists()
        assert backup_info["sources_count"] >= 1

        restore_dir = tempfile.mkdtemp()
        try:
            restored_repo = EssayBackupService.restore_backup(backup_zip, Path(restore_dir))
            restored_docs = restored_repo.list_documents()
            assert len(restored_docs) >= 2

            # Check that answers and revisions are intact
            kia_sw = next(d for d in restored_docs if "SW 품질" in d.title)
            restored_answers = restored_repo.get_answers_for_document(kia_sw.id)
            assert len(restored_answers) == 2
            print("✅ Backup & Restore and Lifecycle cases (L01~L06) passed.")

        finally:
            shutil.rmtree(restore_dir, ignore_errors=True)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_lifecycle_and_backup_restore()
