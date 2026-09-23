"""
Academic Paper QA & Conversational Copilot Agent (Google Gemini Latest API)
Answers user questions in real-time using current paper metadata, page text, formulas, and multi-turn chat history.
"""

import os
import re
import json
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional
from core.searcher import Paper
from core.math_formatter import AcademicMathFormatter

DEFAULT_QA_SYSTEM_PROMPT = """너는 세계 최고 수준의 AI/컴퓨터공학 학술 연구 비서이자 '논문 실시간 질의응답 전문 에이전트(Academic Paper QA Copilot)'야.
사용자가 현재 열람 중인 논문의 메타데이터, 현재 페이지의 본문 텍스트 및 수식 정보, 그리고 이전 대화 기록을 바탕으로 질문에 대해 명확하고 깊이 있는 학술적 한국어로 답변해 줘.

[답변 작성 원칙]:
1. 수식 및 기호 보존 (최우선):
   - 설명에 등장하는 모든 수식, 변수, 기호, 첨자, 그리스 문자(예: $\\hat{A}^i, v_\\theta(x_t, t), \\lambda_1, \\sigma^2, \\Delta t, x_t, \\mathbb{R}^d, \\mathcal{L}$ 등)는 절대로 한글 음역하지 말고 표준 LaTeX `$수식$` 또는 `$$수식$$` 형태로 정확하게 표기할 것.
   - 수식 기호 뒤의 한국어 조사(은/는/이/가/을/를/의/에/와/과/로/으로)는 반드시 닫는 달러 기호($) 바깥에 작성할 것 (올바른 예: '$x_t$는', '$v_\\theta$'의, '$\\theta$에').
2. 전문적이고 유려한 학술적 어조:
   - 핵심 메커니즘, 아키텍처 원리, 수식의 물리적/수학적 의미, 벤치마크 평가 결과 등을 직관적이면서도 엄밀하게 설명할 것.
   - 전문 용어와 약어는 괄호 안에 영문 원문을 병기할 것 (예: 검색 증강 생성(Retrieval-Augmented Generation)).
3. 명확한 구조화:
   - 핵심 요약을 서두에 간결히 제시하고, 필요시 불릿 포인트와 번호 매기기를 통해 가독성을 높일 것.
4. 논문 맥락 충실도:
   - 제공된 논문 정보 및 현재 페이지 텍스트에 기반하여 사실에 입각해 설명할 것.
"""

class PaperChatAgent:
    """Conversational Academic Agent powered by Google Gemini."""

    SUPPORTED_MODELS = [
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]

    @classmethod
    def answer_query(
        cls,
        user_query: str,
        paper: Paper,
        current_page: int = 1,
        page_texts: Optional[List[str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates an academic response to the user's question using Gemini API with paper context.
        """
        clean_q = user_query.strip()
        if not clean_q:
            return {
                "answer": "질문을 입력해 주세요.",
                "model_used": "None",
                "success": False
            }

        # Build context payload
        context_parts = [
            f"📄 [현재 논문 제목]: {paper.title} ({paper.year}년, {paper.venue})",
            f"👥 [저자]: {', '.join(paper.authors[:4])}",
            f"📑 [초록(Abstract)]: {paper.abstract[:800]}",
            f"📍 [현재 열람 중인 페이지]: {current_page}페이지"
        ]

        if page_texts:
            joined_page = "\n".join([f"- {t.strip()}" for t in page_texts if t.strip()][:10])
            context_parts.append(f"📖 [현재 페이지 본문 주요 단락]:\n{joined_page[:1800]}")

        context_str = "\n".join(context_parts)

        # Try Gemini API if API key is provided
        effective_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if effective_key and len(effective_key.strip()) > 10:
            for model_id in cls.SUPPORTED_MODELS:
                try:
                    ans = cls._call_gemini_api(
                        user_query=clean_q,
                        context_str=context_str,
                        chat_history=chat_history or [],
                        api_key=effective_key.strip(),
                        model_id=model_id,
                        system_prompt=system_prompt or DEFAULT_QA_SYSTEM_PROMPT
                    )
                    if ans:
                        formatted_ans = AcademicMathFormatter.format_math_in_text(ans)
                        return {
                            "answer": formatted_ans,
                            "model_used": f"Google {model_id}",
                            "success": True
                        }
                except Exception as e:
                    print(f"Gemini QA model {model_id} error: {e}")

        # No made-up fallback: without a working Gemini call there is no answer to show.
        return {
            "answer": "질문에 답하려면 Gemini API 키가 필요해요." if not effective_key
                      else "Gemini가 답하지 못했어요. 잠시 후 다시 시도해 주세요.",
            "model_used": "None",
            "success": False
        }

    @classmethod
    def _call_gemini_api(
        cls,
        user_query: str,
        context_str: str,
        chat_history: List[Dict[str, str]],
        api_key: str,
        model_id: str,
        system_prompt: str
    ) -> Optional[str]:
        """Calls Google Gemini REST API."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}

        contents = []

        preamble = f"[논문 및 페이지 맥락 정보]:\n{context_str}\n\n위 논문 정보를 바탕으로 사용자의 질문에 답변하십시오."
        contents.append({
            "role": "user",
            "parts": [{"text": preamble}]
        })
        contents.append({
            "role": "model",
            "parts": [{"text": f"네, '{paper_title_short(context_str)}' 논문 및 {extract_page_str(context_str)}의 맥락을 숙지했습니다. 무엇이든 질문하시면 수식과 학술 용어를 명확히 보존하여 답변드리겠습니다."}]
        })

        for turn in chat_history[-6:]:
            role = "user" if turn.get("role") == "user" else "model"
            text = turn.get("text") or turn.get("content") or ""
            if text.strip():
                contents.append({
                    "role": role,
                    "parts": [{"text": text.strip()}]
                })

        contents.append({
            "role": "user",
            "parts": [{"text": user_query}]
        })

        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 2048
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        return None
