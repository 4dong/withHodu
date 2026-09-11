"""
Unit and Integration Tests for EssayRepository (P1 Milestone)
"""

import os
import sys
import tempfile
import shutil
import json
from pathlib import Path

# Ensure workspace root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.essay.models import Document, new_uuid
from core.essay.repository import EssayRepository
from core.essay.seed import seed_data_file


def test_repository_lifecycle():
    temp_dir = tempfile.mkdtemp()
    try:
        repo = EssayRepository(archive_root=temp_dir)

        # 1. Source file atomic storage and deduplication
        dummy_bytes = b"Hello essay source image test bytes"
        src1 = repo.store_source_file(dummy_bytes, "test_img1.png", "image/png")
        assert src1.content_sha256 is not None
        assert src1.byte_size == len(dummy_bytes)

        # Deduplication: same bytes return existing source
        src2 = repo.store_source_file(dummy_bytes, "test_img1_copy.png", "image/png")
        assert src1.id == src2.id
        assert src1.content_sha256 == src2.content_sha256

        # Check file exists on disk
        stored_path = repo.get_source_file_path(src1.storage_key)
        assert stored_path is not None and stored_path.exists()

        # 2. Document CRUD
        doc = Document(
            id=new_uuid(),
            title="현대자동차 R&D 자소서",
            company="현대자동차",
            division="R&D본부",
            role="자율주행 SW",
            collection="own_draft",
            grouping_status="confirmed",
            completeness="complete"
        )
        created_doc = repo.create_document(doc)
        assert created_doc.id == doc.id

        retrieved = repo.get_document(doc.id)
        assert retrieved is not None
        assert retrieved.title == "현대자동차 R&D 자소서"

        # List
        doc_list = repo.list_documents(company="현대자동차")
        assert len(doc_list) == 1
        assert doc_list[0].id == doc.id

        # 3. Answer & Revisions
        ans, rev1 = repo.create_answer(
            document_id=doc.id,
            question_number=1,
            question_text="지원동기를 서술하시오.",
            body_text="첫 번째 초안 텍스트입니다.",
            origin="manual",
            review_status="needs_user_review"
        )
        assert ans.document_id == doc.id
        assert rev1.body_text == "첫 번째 초안 텍스트입니다."
        assert rev1.review_status == "needs_user_review"

        # Add revision 2 (Append-only)
        rev2 = repo.add_revision(
            answer_id=ans.id,
            parent_revision_id=rev1.id,
            question_text="지원동기를 서술하시오.",
            body_text="두 번째로 수정한 초안 텍스트입니다.",
            origin="rewrite",
            review_status="approved",
            set_as_current=True
        )
        assert rev2.parent_revision_id == rev1.id
        all_revs = repo.list_revisions(ans.id)
        assert len(all_revs) == 2
        # Previous revision is immutable
        assert all_revs[0].body_text == "첫 번째 초안 텍스트입니다."

        answers = repo.get_answers_for_document(doc.id)
        assert len(answers) == 1
        assert answers[0][1].id == rev2.id

        # 4. Tags
        t1 = repo.ensure_tag("tech_tool", "PyTorch")
        assignment = repo.assign_tag(doc.id, "document", t1.canonical_id, origin="manual", status="accepted")
        assert assignment.tag_id == "tech_tool:PyTorch"
        doc_tags = repo.get_tags_for_target(doc.id)
        assert len(doc_tags) == 1
        assert doc_tags[0][0].label == "PyTorch"
        assert doc_tags[0][1].status == "accepted"

        # 5. Export Markdown, TXT, ZIP
        md = repo.export_document_markdown(doc.id)
        assert "현대자동차 R&D 자소서" in md
        assert "두 번째로 수정한 초안 텍스트입니다." in md

        txt = repo.export_document_txt(doc.id)
        assert "[현대자동차 R&D 자소서]" in txt

        zip_p = repo.export_document_zip(doc.id)
        assert zip_p.exists()
        assert zip_p.stat().st_size > 0

        # 6. Soft Delete (Tombstone)
        repo.delete_document(doc.id)
        assert repo.get_document(doc.id) is None
        assert repo.get_document(doc.id, include_deleted=True) is not None

        # 7. Seed import and idempotency
        seed_path = seed_data_file("seed.json")
        if seed_path:
            with open(seed_path, "r", encoding="utf-8") as f:
                seed_data = json.load(f)

            res1 = repo.import_seed_data(seed_data)
            assert res1["documents"] == 2
            assert res1["answers"] == 4

            # Verify seed documents preserved provisional grouping and needs_user_review
            seed_docs = repo.list_documents()
            assert len(seed_docs) >= 2
            kia_sw = next(d for d in seed_docs if "SW 품질" in d.title)
            assert kia_sw.grouping_status == "provisional"
            assert kia_sw.collection == "reference"

            answers_kia = repo.get_answers_for_document(kia_sw.id)
            assert len(answers_kia) == 2  # Q1, Q3
            for _, rev in answers_kia:
                assert rev.review_status == "needs_user_review"

            # Check Q2 missing completeness indicator
            assert kia_sw.completeness == "partial"

            # Re-importing should NOT duplicate documents or answers
            res2 = repo.import_seed_data(seed_data)
            assert res2["documents"] == 0
            assert res2["answers"] == 0

        print("✅ EssayRepository lifecycle & seed import tests passed.")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_repository_lifecycle()
