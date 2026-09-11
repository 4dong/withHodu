"""
Unit & Integration Test for PaperChatAgent
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.searcher import Paper
from core.qa_agent import PaperChatAgent

def test_paper_chat_agent():
    mock_paper = Paper(
        id="test_mock_paper_01",
        title="CosyVoice 3: Scalable Streaming Speech Synthesis with Large Language Models",
        authors=["Zhihao Du", "Qian Chen", "Shiliang Zhang"],
        year=2025,
        abstract="We present CosyVoice 3, a state-of-the-art multilingual speech synthesis model with zero-shot in-context cloning and streaming capabilities.",
        venue="arXiv Preprint",
        citation_count=42,
        pdf_url="https://arxiv.org/pdf/2407.05407.pdf",
        doi=None,
        source="arXiv",
        url="https://arxiv.org/abs/2407.05407"
    )

    page_texts = [
        "In this section, we formulate the flow matching loss L_FM(theta) = E_{t, x_0, x_1} [ || v_theta(x_t, t) - (x_1 - x_0) ||^2 ].",
        "The model achieves zero-shot speaker adaptation with less than 3 seconds of reference audio."
    ]

    # Math/Formula QA Query
    res_math = PaperChatAgent.answer_query(
        user_query="이 1페이지의 핵심 손실 함수 수식과 theta의 의미를 설명해줘",
        paper=mock_paper,
        current_page=1,
        page_texts=page_texts,
        chat_history=[]
    )
    assert res_math.get("success") is True, f"Failed math query: {res_math}"
    assert "$" in res_math.get("answer"), "LaTeX math delimiters missing in answer"

    # Contribution QA Query
    res_contrib = PaperChatAgent.answer_query(
        user_query="이 논문의 핵심 기여점과 기존 모델 대비 차별점 요약해줘",
        paper=mock_paper,
        current_page=1,
        page_texts=page_texts,
        chat_history=[
            {"role": "user", "text": "이 논문 어떤 주제야?"},
            {"role": "assistant", "text": "음성 합성 및 제로샷 음성 복제 모델입니다."}
        ]
    )
    assert res_contrib.get("success") is True
    assert len(res_contrib.get("answer", "")) > 50

    # Empty Query Defense
    res_empty = PaperChatAgent.answer_query(
        user_query="",
        paper=mock_paper,
        current_page=1
    )
    assert res_empty.get("success") is False

if __name__ == "__main__":
    test_paper_chat_agent()
    print("✅ PaperChatAgent tests passed.")
