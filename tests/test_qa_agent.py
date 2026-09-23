"""
PaperChatAgent: Gemini answers with the page as context; without it there is no answer, never a template.
"""

import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.searcher import Paper
from core.qa_agent import PaperChatAgent

PAPER = Paper(
    id="test_mock_paper_01",
    title="CosyVoice 3: Scalable Streaming Speech Synthesis with Large Language Models",
    authors=["Zhihao Du", "Qian Chen", "Shiliang Zhang"],
    year=2025,
    abstract="We present CosyVoice 3, a multilingual speech synthesis model with zero-shot cloning.",
    venue="arXiv Preprint",
    citation_count=42,
    pdf_url="https://arxiv.org/pdf/2407.05407.pdf",
    doi=None,
    source="arXiv",
    url="https://arxiv.org/abs/2407.05407"
)
PAGE = [
    "In this section, we formulate the flow matching loss L_FM(theta).",
    "The model achieves zero-shot speaker adaptation with less than 3 seconds of reference audio.",
]


def ask(question, **kwargs):
    return PaperChatAgent.answer_query(user_query=question, paper=PAPER, current_page=1, page_texts=PAGE, **kwargs)


def test_gemini_answer_is_returned_with_the_page_as_context():
    with mock.patch.object(PaperChatAgent, "_call_gemini_api", return_value="손실 함수는 $L_{FM}(\\theta)$입니다.") as call:
        result = ask("이 페이지의 손실 함수는?", api_key="k" * 30)
    assert result["success"] is True
    assert "$" in result["answer"]
    assert "zero-shot speaker adaptation" in call.call_args.kwargs["context_str"]


def test_without_a_key_there_is_no_made_up_answer():
    with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
        result = ask("이 논문의 핵심 기여점은?")
    assert result["success"] is False
    assert "API 키" in result["answer"]


def test_a_failed_gemini_call_is_reported_not_papered_over():
    with mock.patch.object(PaperChatAgent, "_call_gemini_api", return_value=None):
        result = ask("요약해 줘", api_key="k" * 30)
    assert result["success"] is False


def test_empty_question_is_rejected():
    assert ask("")["success"] is False
