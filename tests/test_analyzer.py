"""Comparison reports come from Gemini only; without it nothing is written that reads like an analysis."""
from unittest import mock

from core.analyzer import MultiPaperComparativeAgent

PAPERS = [{"title": "Paper A", "abstract": "A"}, {"title": "Paper B", "abstract": "B"}]


def test_without_a_key_no_report_is_made_up():
    result = MultiPaperComparativeAgent.analyze_papers(PAPERS, api_key=None)
    assert result["success"] is False
    assert result["report_markdown"] == ""
    assert "API 키" in result["error"]


def test_a_failed_gemini_call_is_not_replaced_by_a_template():
    with mock.patch.object(MultiPaperComparativeAgent, "_run_gemini", return_value=None):
        result = MultiPaperComparativeAgent.analyze_papers(PAPERS, api_key="k" * 30)
    assert result["success"] is False and result["report_markdown"] == ""


def test_gemini_report_is_returned():
    with mock.patch.object(MultiPaperComparativeAgent, "_run_gemini", return_value="# 비교\n내용") as run:
        result = MultiPaperComparativeAgent.analyze_papers(PAPERS, custom_question="구조", api_key="k" * 30)
    assert result["success"] is True and "비교" in result["report_markdown"]
    assert run.call_args.args[0]["user_focus_question"] == "구조"
