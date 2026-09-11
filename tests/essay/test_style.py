"""
Unit and Integration Tests for Style Rewriter, Fact Preservation, and Revision Guard (P5 Milestone)
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.essay.repository import EssayRepository
from core.essay.style import (
    EssayStyleService, MockStyleRewriter, StyleValidator,
    RevisionConflictError, FactExtractor
)


def test_style_evaluation_cases():
    temp_dir = tempfile.mkdtemp()
    try:
        repo = EssayRepository(archive_root=temp_dir)
        style_svc = EssayStyleService(repo, rewriter=MockStyleRewriter())

        # Create user draft document
        from core.essay.models import Document, new_uuid
        doc = repo.create_document(
            Document(
                id=new_uuid(),
                title="내 초안",
                company="기아",
                division="SW",
                role="품질",
                collection="own_draft",
                author="홍길동",
                recruitment_year=2026,
                outcome="unknown",
                grouping_status="confirmed",
                completeness="complete"
            )
        )

        # S01: Preservation of meetings/design share, forbidden reference facts (team lead, 15 months, PyTorch, etc.)
        ans1, rev1 = repo.create_answer(
            document_id=doc.id,
            question_number=1,
            question_text="협업 경험",
            body_text="저는 동아리 회의록을 정리하고 설계 변경 사항을 팀원에게 공유했습니다.",
            origin="manual"
        )
        prop1 = style_svc.generate_rewrite_proposal(
            input_revision_id=rev1.id,
            style_name="두괄식 직무 중심",
            mode="strict_preserve"
        )
        assert "회의록" in prop1.output_text
        assert "설계 변경 사항" in prop1.output_text
        for forbidden in ["팀장", "15개월", "120개", "PyTorch", "2.45mm", "25%"]:
            assert forbidden not in prop1.output_text

        # S02: Numerical fidelity 120, 2.45mm, 3.20mm, without exaggerated claims
        ans2, rev2 = repo.create_answer(
            document_id=doc.id,
            question_number=2,
            question_text="계측 모델",
            body_text="120개의 파형으로 모델을 만들었으며 평균 오차는 2.45mm였습니다. 기존 시스템은 3.20mm였습니다.",
            origin="manual"
        )
        prop2 = style_svc.generate_rewrite_proposal(
            input_revision_id=rev2.id,
            style_name="간결한 문체",
            mode="strict_preserve"
        )
        assert "120" in prop2.output_text
        assert "2.45mm" in prop2.output_text
        assert "3.20mm" in prop2.output_text
        assert "정확도 25% 상승" not in prop2.output_text
        assert "현장 도입 완료" not in prop2.output_text

        # S03: Preservation of negative / unresolved facts (do not falsely resolve)
        ans3, rev3 = repo.create_answer(
            document_id=doc.id,
            question_number=3,
            question_text="문제 해결",
            body_text="로그를 수집했지만 원인은 확정하지 못했습니다.",
            origin="manual"
        )
        prop3 = style_svc.generate_rewrite_proposal(
            input_revision_id=rev3.id,
            style_name="성과 중심",
            mode="strict_preserve"
        )
        assert "미확정" in prop3.output_text or "확정하지 못" in prop3.output_text
        assert "원인 규명" not in prop3.output_text
        assert "문제 해결 완료" not in prop3.output_text

        # S04: Max chars constraint conflict
        ans4, rev4 = repo.create_answer(
            document_id=doc.id,
            question_number=4,
            question_text="설계 경험",
            body_text="15개월 동안 차량 프레임을 설계하고 CAD로 부품 간섭을 검증했습니다.",
            origin="manual"
        )
        prop4 = style_svc.generate_rewrite_proposal(
            input_revision_id=rev4.id,
            style_name="담백한 문체",
            max_chars=5
        )
        val4 = json.loads(prop4.validation_json)
        assert val4["can_accept"] is False
        assert "너무 짧아" in val4["length_warning"] or val4["length_satisfied"] is False

        # S05: Revision conflict protection on accept
        # 1. Accept valid proposal for ans1
        accepted_rev = style_svc.accept_proposal(prop1, expected_input_revision_id=rev1.id)
        assert accepted_rev.parent_revision_id == rev1.id
        assert accepted_rev.origin == "rewrite"

        # 2. Try to accept prop1 again using the old rev1 as expected
        try:
            style_svc.accept_proposal(prop1, expected_input_revision_id=rev1.id)
            assert False, "Should raise RevisionConflictError because current revision has moved forward to accepted_rev"
        except RevisionConflictError as e:
            assert "다른 편집 작업으로 인해" in str(e)

        print("✅ All Style rewriter evaluation cases (S01~S05) and revision conflict guard passed.")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_style_evaluation_cases()
