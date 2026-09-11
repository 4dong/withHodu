"""
Unit and Integration Tests for Tagging, Chunking, and Retrieval (P3 Milestone)
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.essay.repository import EssayRepository
from core.essay.tagging import TagService
from core.essay.chunking import EssayChunker
from core.essay.embedding import MockEmbeddingProvider
from core.essay.retrieval import EssaySearchEngine
from tests.essay.seed_fixtures import load_seed_json


def test_tagging_chunking_retrieval():
    temp_dir = tempfile.mkdtemp()
    try:
        repo = EssayRepository(archive_root=temp_dir)
        tag_svc = TagService(repo)

        # 1. Tag dictionary & alias tests
        resolved = tag_svc.resolve_tag("파이토치")
        assert resolved is not None
        assert resolved.label == "PyTorch"
        assert resolved.canonical_id == "tech_tool:PyTorch"

        # Deterministic extraction
        text = "CANalyzer와 FRAM을 사용하여 차량 제어기의 이상 로그를 분석했습니다."
        extracted = tag_svc.extract_deterministic_tags(text)
        labels = [t.label for t, _ in extracted]
        assert "CANalyzer" in labels
        assert "FRAM" in labels

        # 2. Chunking tests
        chunks = EssayChunker.chunk_revision(
            revision_id="rev-1",
            answer_id="ans-1",
            document_id="doc-1",
            body_text=text
        )
        assert len(chunks) == 1
        assert chunks[0].kind == "answer"
        assert chunks[0].start_char == 0
        assert chunks[0].end_char == len(text)

        # 3. Load seed data and prepare approved test fixture
        seed_data = load_seed_json("seed.json")

        repo.import_seed_data(seed_data)

        # Map external IDs to internal IDs for verification
        ext_map = {}
        with repo.get_connection() as conn:
            cur = conn.execute("SELECT external_id, internal_id FROM seed_imports")
            for r in cur.fetchall():
                ext_map[r["external_id"]] = r["internal_id"]

        # Mark revisions as approved for indexing test
        with repo.get_connection() as conn:
            conn.execute("UPDATE answer_revisions SET review_status = 'approved'")
            conn.commit()

        # Initialize search engine with MockEmbeddingProvider
        embed_provider = MockEmbeddingProvider(dimension=128)
        engine = EssaySearchEngine(repo, embedding_provider=embed_provider)
        engine.index_all_approved(allow_unreviewed=False)

        # 4. Validate evaluation queries from data/evaluation.json
        eval_data = load_seed_json("evaluation.json")

        retrieval_cases = eval_data.get("retrieval", [])
        passed_evals = 0

        for case in retrieval_cases:
            cid = case["id"]
            query = case["query"]
            expected_ext_ids = case.get("expected_answer_ids", [])
            filters = {}

            if "filters" in case:
                f_doc = case["filters"].get("document_id")
                if f_doc and f_doc in ext_map:
                    filters["document_id"] = ext_map[f_doc]

            search_res = engine.search(query=query, filters=filters, limit=5)
            assert len(search_res.hits) > 0, f"Query failed to produce hits: {query}"

            # Check if expected answer id is in top hits
            top_ans_ids = [h.answer_id for h in search_res.hits]
            matched = False
            for exp_ext in expected_ext_ids:
                if exp_ext in ext_map and ext_map[exp_ext] in top_ans_ids:
                    matched = True
                    break

            assert matched, f"Case {cid} ({query}): Expected {expected_ext_ids} in top hits, got {[h.question_text[:20] for h in search_res.hits]}"
            passed_evals += 1

        print(f"✅ All {passed_evals} retrieval test cases from evaluation.json passed successfully!")

        # 5. Test Fallback Mode (No Embedding Provider)
        keyword_engine = EssaySearchEngine(repo, embedding_provider=None)
        res_kw = keyword_engine.search("CANalyzer FRAM")
        assert res_kw.mode == "keyword_only"
        assert len(res_kw.hits) > 0
        assert "CANalyzer" in res_kw.hits[0].text

        # 6. Test Outdated Revision Exclusion
        # Update kia-sw-q1 with revision 2
        ans_internal_id = ext_map["kia-sw-q1"]
        ans = repo.get_answer(ans_internal_id)
        old_rev_id = ans.current_revision_id

        new_rev = repo.add_revision(
            answer_id=ans_internal_id,
            parent_revision_id=old_rev_id,
            question_text="기아 지원동기 개정판",
            body_text="완전히 새로 작성된 자율주행 SW 품질 역량 본문입니다.",
            origin="manual",
            review_status="approved",
            set_as_current=True
        )
        engine.index_revision(new_rev.id)

        # Search for old text "PV5" -> should no longer find kia-sw-q1
        sw_doc_internal_id = ext_map["kia-sw"]
        res_old = engine.search("PV5", filters={"document_id": sw_doc_internal_id})
        # kia-sw-q1 has been replaced so its chunks should not be found
        found_rev_ids = [h.revision_id for h in res_old.hits]
        assert old_rev_id not in found_rev_ids

        # Search for new text
        res_new = engine.search("자율주행 SW 품질 역량", filters={"document_id": sw_doc_internal_id})
        assert len(res_new.hits) > 0
        assert res_new.hits[0].revision_id == new_rev.id

        print("✅ Tagging, Chunking, Retrieval, and Revision-Exclusion tests passed.")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_tagging_chunking_retrieval()
