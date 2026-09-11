"""
Unit and Integration Tests for Grounded RAG, Citation Verification, and Safety (P4 Milestone)
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.essay.repository import EssayRepository
from core.essay.embedding import MockEmbeddingProvider
from core.essay.retrieval import EssaySearchEngine
from core.essay.rag import EssayRAGService, MockRAGGenerator, Citation
from tests.essay.seed_fixtures import load_seed_json


def test_rag_evaluation_cases():
    temp_dir = tempfile.mkdtemp()
    try:
        repo = EssayRepository(archive_root=temp_dir)

        # Import seed data
        seed_data = load_seed_json("seed.json")

        repo.import_seed_data(seed_data)

        # Mark revisions as approved for indexing
        with repo.get_connection() as conn:
            conn.execute("UPDATE answer_revisions SET review_status = 'approved'")
            conn.commit()

        embed_provider = MockEmbeddingProvider(dimension=128)
        search_engine = EssaySearchEngine(repo, embedding_provider=embed_provider)
        search_engine.index_all_approved()

        rag_svc = EssayRAGService(repo, search_engine, generator=MockRAGGenerator())

        # Load evaluation cases
        eval_data = load_seed_json("evaluation.json")

        rag_cases = eval_data.get("rag", [])

        # Q01: Missing question Q2
        q01 = next(c for c in rag_cases if c["id"] == "Q01")
        ans01 = rag_svc.answer_question(q01["query"])
        assert ans01.status == q01["expected_status"]
        assert "Q2" in ans01.answer and "누락" in ans01.answer

        # Q02: Unknown recruitment/acceptance year
        q02 = next(c for c in rag_cases if c["id"] == "Q02")
        ans02 = rag_svc.answer_question(q02["query"])
        assert ans02.status == q02["expected_status"]
        assert "연도" in ans02.answer or "합격" in ans02.answer

        # Q03: Incomplete FRAM resolution
        q03 = next(c for c in rag_cases if c["id"] == "Q03")
        ans03 = rag_svc.answer_question(q03["query"])
        assert ans03.status == "answered"
        assert len(ans03.citations) > 0
        assert any("최종 조치" in lim for lim in ans03.limitations)

        # Q04: Numerical facts in measurement case
        q04 = next(c for c in rag_cases if c["id"] == "Q04")
        ans04 = rag_svc.answer_question(q04["query"])
        assert ans04.status == "answered"
        for req in q04["required_strings"]:
            assert req in ans04.answer

        # Q05: Own experience filter vs reference candidate
        q05 = next(c for c in rag_cases if c["id"] == "Q05")
        ans05 = rag_svc.answer_question(q05["query"], filters=q05.get("filters"))
        assert ans05.status == q05["expected_status"]

        # Q06: Prompt injection in evidence text
        q06 = next(c for c in rag_cases if c["id"] == "Q06")
        ans06 = rag_svc.generator.generate(
            "이 자소서의 내용을 요약해 줘",
            evidence_pack=[{"text": q06["synthetic_evidence"]}]
        )
        assert ans06.status == "answered"
        assert "차단" in ans06.limitations[0] or "명령어" in ans06.limitations[0]

        # 7. Substring Citation Verification
        # Positive case: citation quote matches body_text substring
        kia_sw_rev = repo.list_documents()[0]
        answers = repo.get_answers_for_document(kia_sw_rev.id)
        test_ans, test_rev = answers[0]
        valid_quote = test_rev.body_text[:20]

        valid_cit = Citation(
            id="C1",
            answer_id=test_ans.id,
            revision_id=test_rev.id,
            document_id=kia_sw_rev.id,
            source_id="img-01",
            quote=valid_quote
        )
        verified = rag_svc._verify_citations([valid_cit])
        assert len(verified) == 1

        # Negative case: fabricated quote not in body_text
        fake_cit = Citation(
            id="C2",
            answer_id=test_ans.id,
            revision_id=test_rev.id,
            document_id=kia_sw_rev.id,
            source_id="img-01",
            quote="이 문구는 본문에 절대 존재하지 않는 날조된 인용구입니다."
        )
        rejected = rag_svc._verify_citations([fake_cit])
        assert len(rejected) == 0

        # Deleted document citation invalidation
        repo.delete_document(kia_sw_rev.id)
        invalidated = rag_svc._verify_citations([valid_cit])
        assert len(invalidated) == 0

        print("✅ All RAG evaluation cases and citation verification tests passed.")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_rag_evaluation_cases()
