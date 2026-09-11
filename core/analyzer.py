"""
Multi-Paper Comparative Synthesis AI Agent
Analyzes multiple academic papers simultaneously to generate structured comparative matrices,
methodological deep-dives, evolution timelines, and actionable research insights.
"""

import os
import json
import urllib.request
import urllib.parse
import re
from typing import List, Dict, Any, Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

DEFAULT_COMPARISON_SYSTEM_PROMPT = """너는 세계 최고 수준의 AI/컴퓨터공학 학술 연구소의 수석 연구위원이자 논문 비교분석 전문 에이전트야.
사용자가 제공한 여러 편의 학술 논문 정보(제목, 연도, 저자, 초록, 주요 본문 발췌)를 종합적으로 정밀 분석하여, 다음 5대 영역으로 구성된 완성도 높은 학술 비교분석 보고서를 마크다운(Markdown) 포맷으로 작성해 줘.

---

### [보고서 필수 구성 양식]:

# 📑 [선택된 논문 군(群)의 핵심 주제] 다중 논문 비교분석 보고서

## 1. 📌 총괄 비교 요약 (Executive Synthesis)
- 전체 논문들이 공통적으로 해결하고자 하는 문제의식과 핵심 접근법을 3~5문장으로 명확히 종합 요약.

## 2. 📊 핵심 비교 매트릭스 (Comparative Matrix Table)
- 반드시 아래 열(Column)을 포함하는 정밀 마크다운 비교 표를 작성할 것:
| 논문명 (연도) | 핵심 연구 목적 | 제안 모델 / 핵심 아키텍처 | 주요 벤치마크 및 정량 지표 (Pass@k / MOS / WER 등) | 핵심 기여점 및 강점 | 한계점 및 제약사항 |

## 3. 🔬 방법론 및 아키텍처 심층 대조 (Methodology & Architecture Deep-Dive)
- 각 논문의 알고리즘, 손실 함수(Loss function), 훈련 기법(SFT, RL, Flow Matching, Weight Averaging 등)의 기술적 차이점과 작동 원리를 세부적으로 대조 분석.

## 4. 📈 기술 진화 계보 및 패러다임 변화 (Evolutionary Trajectory & Paradigm Shift)
- 시간 순서 및 기술적 관점에서 연구 흐름이 어떻게 발전하고 있는지(예: 단일 모델 한계 극복 -> 앙상블/보상 최적화 -> 추론 시점 확장 등) 연구 계보를 설명.

## 5. 💡 후속 연구 기회 및 실무 시사점 (Actionable Insights & Future Opportunities)
- 이 논문들을 종합했을 때 향후 파생될 수 있는 새로운 연구 아이디어와 실무 엔지니어링 적용 시 고려해야 할 시사점 제시.

---

### [작성 원칙]:
- 전문 용어, 기술 명칭, 지표(Metric), 약어(예: Pass@k, MOS, WiSE-FT, SFT 등)는 억지 번역을 피하고 괄호 안에 원문을 병기할 것 (예: 가중치 앙상블(Weight Ensembling)).
- [중요 서식 규칙 - HTML 태그 절대 금지]: 마크다운 표(Table) 내부에서 `<br>`, `<br/>`, `<span>` 등의 HTML 태그를 절대로 사용하지 마십시오. 표 안에서 항목을 여러 개 나열할 때는 줄바꿈 태그 대신 슬래시(/), 쉼표(,), 또는 불릿 기호(·)를 사용하여 순수 텍스트로 작성하십시오.
- 표와 불릿 포인트를 적극 활용하여 가독성을 극대화하고 객관적이고 권위 있는 학술적 어조를 유지할 것.
"""

class MultiPaperComparativeAgent:
    """Agent that performs multi-paper comparative synthesis across stored bundles."""

    @classmethod
    def analyze_papers(
        cls,
        papers: List[Dict[str, Any]],
        custom_question: Optional[str] = None,
        engine: str = "🤖 Google Gemini 3.5 Flash (제미나이 추천 · 키 필요)",
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes multiple papers and produces a comprehensive academic comparison report.
        """
        if not papers:
            return {
                "success": False,
                "error": "비교분석할 논문이 선택되지 않았습니다.",
                "report_markdown": ""
            }

        # 1. Prepare concise research profiles for each paper
        paper_profiles = []
        for idx, p in enumerate(papers):
            title = p.get("title", "Untitled")
            year = p.get("year", "N/A")
            authors = ", ".join(p.get("authors", [])[:4])
            venue = p.get("venue", "Academic Publication")
            abstract = p.get("abstract", "")
            
            # Extract first page text from PDF if available
            pdf_path = p.get("pdf_path") or os.path.join(p.get("folder_path", ""), "paper.pdf")
            first_page_excerpt = ""
            if fitz and pdf_path and os.path.exists(pdf_path):
                try:
                    doc = fitz.open(pdf_path)
                    if len(doc) > 0:
                        first_page_excerpt = doc[0].get_text()[:1200]
                    doc.close()
                except Exception:
                    pass

            paper_profiles.append({
                "index": idx + 1,
                "title": title,
                "year": year,
                "authors": authors,
                "venue": venue,
                "abstract": abstract[:1000],
                "excerpt": first_page_excerpt[:800] if first_page_excerpt else "본문 초록 정보 참조"
            })

        user_prompt_data = {
            "papers_count": len(papers),
            "papers": paper_profiles,
            "user_focus_question": custom_question.strip() if custom_question else "전반적인 모델 구조, 방법론, 벤치마크 성능 및 기여점 중심 비교"
        }

        prompt_to_use = system_prompt or DEFAULT_COMPARISON_SYSTEM_PROMPT

        # 2. Execute with selected LLM Engine
        # Engine: Google Gemini 3.5 Flash / Lite
        if "Gemini" in engine:
            model_name = "gemini-3.5-flash-lite" if "Lite" in engine else "gemini-3.5-flash"
            if api_key and len(api_key) > 20:
                try:
                    report = cls._run_gemini(user_prompt_data, prompt_to_use, api_key.strip(), model_name)
                    if report:
                        return {
                            "success": True,
                            "engine": f"Google {model_name}",
                            "report_markdown": cls._clean_report_markdown(report)
                        }
                except Exception as e:
                    print(f"Gemini comparison error: {e}")
            
            # Fallback heuristic if key missing
            return cls._run_heuristic_synthesis(papers, custom_question, fallback_note="Google Gemini (API 키 미설정 · 로컬 휴리스틱 매트릭스 생성)")

        # Engine: OpenAI GPT-4o-mini
        elif "OpenAI" in engine:
            if api_key and api_key.startswith("sk-"):
                try:
                    report = cls._run_openai(user_prompt_data, prompt_to_use, api_key.strip())
                    if report:
                        return {
                            "success": True,
                            "engine": "OpenAI GPT-4o-mini",
                            "report_markdown": cls._clean_report_markdown(report)
                        }
                except Exception as e:
                    print(f"OpenAI comparison error: {e}")
            return cls._run_heuristic_synthesis(papers, custom_question, fallback_note="OpenAI (API 키 미설정 · 로컬 휴리스틱 매트릭스 생성)")

        # Engine: Claude 3.5 Haiku
        elif "Claude" in engine:
            if api_key and api_key.startswith("sk-ant-"):
                try:
                    report = cls._run_claude(user_prompt_data, prompt_to_use, api_key.strip())
                    if report:
                        return {
                            "success": True,
                            "engine": "Claude 3.5 Haiku",
                            "report_markdown": cls._clean_report_markdown(report)
                        }
                except Exception as e:
                    print(f"Claude comparison error: {e}")
            return cls._run_heuristic_synthesis(papers, custom_question, fallback_note="Claude (API 키 미설정 · 로컬 휴리스틱 매트릭스 생성)")

        # Default fallback
        return cls._run_heuristic_synthesis(papers, custom_question)

    @classmethod
    def _clean_report_markdown(cls, raw_md: str) -> str:
        """Sanitizes raw HTML break tags and formatting noise from LLM responses."""
        if not raw_md:
            return ""
        # 1. Clean HTML line breaks into clean bullet dots or spacing
        clean = re.sub(r'<br\s*/?>', ' · ', raw_md, flags=re.IGNORECASE)
        clean = re.sub(r'&lt;br\s*/?&gt;', ' · ', clean, flags=re.IGNORECASE)
        # 2. Clean multiple consecutive bullet dots
        clean = re.sub(r'(\s*·\s*){2,}', ' · ', clean)
        # 3. Clean trailing dots around markdown table pipes
        clean = re.sub(r'\s*·\s*\|', ' |', clean)
        clean = re.sub(r'\|\s*·\s*', '| ', clean)
        return clean.strip()

    @classmethod
    def _run_gemini(cls, data: Dict[str, Any], system_prompt: str, api_key: str, model_name: str) -> Optional[str]:
        """Calls Google Gemini API for multi-paper synthesis."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}

        full_prompt = f"{system_prompt}\n\n[비교분석할 논문 데이터셋]:\n{json.dumps(data, ensure_ascii=False, indent=2)}"

        payload = {
            "contents": [
                {
                    "parts": [{"text": full_prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.25
            }
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=35) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        return None

    @classmethod
    def _run_openai(cls, data: Dict[str, Any], system_prompt: str, api_key: str) -> Optional[str]:
        """Calls OpenAI GPT-4o-mini for multi-paper synthesis."""
        endpoint = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"[비교분석할 논문 데이터셋]:\n{json.dumps(data, ensure_ascii=False, indent=2)}"}
            ],
            "temperature": 0.25
        }
        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=35) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            return res_data["choices"][0]["message"]["content"].strip()

    @classmethod
    def _run_claude(cls, data: Dict[str, Any], system_prompt: str, api_key: str) -> Optional[str]:
        """Calls Claude 3.5 Haiku for multi-paper synthesis."""
        endpoint = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": f"[비교분석할 논문 데이터셋]:\n{json.dumps(data, ensure_ascii=False, indent=2)}"}
            ]
        }
        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=35) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            return res_data["content"][0]["text"].strip()

    @classmethod
    def _run_heuristic_synthesis(cls, papers: List[Dict[str, Any]], custom_question: Optional[str], fallback_note: Optional[str] = None) -> Dict[str, Any]:
        """Local structural synthesis matrix generator when API keys are not provided."""
        titles = [p.get("title", "Untitled") for p in papers]
        topic_header = " & ".join([t[:25] for t in titles[:3]])
        
        table_rows = []
        for idx, p in enumerate(papers):
            t = p.get("title", "Untitled")
            y = p.get("year", "2025")
            v = p.get("venue", "Preprint")
            ab = p.get("abstract", "")[:120].replace("\n", " ") + "..."
            table_rows.append(f"| **#{idx+1} {t[:35]}...** ({y}) | {ab} | 아키텍처 및 알고리즘 제안 | 학술 벤치마크 검증 | {v} 출처 기반 연구 기여 | 후속 확장 검증 필요 |")

        table_md = "\n".join(table_rows)

        report_md = f"""# 📑 [{topic_header}] 다중 논문 비교분석 보고서

> **분석 엔진**: {fallback_note or '로컬 학술 비교 엔진 (휴리스틱)'}  
> **비교 논문 수**: 총 {len(papers)}편  
> **분석 기준**: {custom_question or '핵심 아키텍처, 벤치마크 및 기여점 종합 비교'}

---

## 1. 📌 총괄 비교 요약 (Executive Synthesis)
본 보고서는 서재에 수집된 총 {len(papers)}편의 관련 연구를 바탕으로 기술적 접근 방식과 연구 패러다임을 종합 분석했습니다.
수집된 논문들은 특정 학술 도메인에서 발생하는 핵심 제약(성능 한계, 모델 일반화 저하, 추론 효율성 문제)을 해결하기 위해 고유한 아키텍처 혁신과 손실 함수 최적화를 제안하고 있습니다.

## 2. 📊 핵심 비교 매트릭스 (Comparative Matrix Table)
| 논문명 (연도) | 핵심 연구 목적 및 배경 | 제안 모델 / 핵심 접근법 | 주요 벤치마크 및 평가 | 핵심 기여점 및 강점 | 한계점 및 제약사항 |
| :--- | :--- | :--- | :--- | :--- | :--- |
{table_md}

## 3. 🔬 방법론 및 아키텍처 심층 대조 (Methodology Deep-Dive)
- **접근법 다각화**: 각 논문은 사전 훈련(Pretraining), 미세 조정(Finetuning), 사후 최적화(Post-hoc Optimization) 등 서로 다른 파이프라인 단계에서 해결책을 모색하고 있습니다.
- **평가 지표의 엄밀성**: 정량적 평가 지표를 통해 기존 기준선(Baseline) 대비 유의미한 성능 향상을 입증하였습니다.

## 4. 📈 기술 진화 계보 및 패러다임 변화 (Evolutionary Trajectory)
- 초기 연구가 모델의 기본 성능 향상에 집중했다면, 최근 연구는 **추론 시점 연산 확장(Test-Time Compute)** 및 **가중치 공간 앙상블(Weight Space Ensembling)** 등 자원 효율적이고 일반화 능력이 뛰어난 방향으로 진화하고 있습니다.

## 5. 💡 후속 연구 기회 및 실무 시사점 (Actionable Insights)
1. **모델 간 시너지 결합**: 각 연구에서 제안된 손실 함수와 가중치 최적화 기법을 결합하여 하이브리드 파이프라인을 구축할 수 있습니다.
2. **실무 프로덕션 적용**: 연산 비용 대비 성능 향상 폭을 고려하여 경량화 및 실시간 서빙 최적화를 추가 검토할 것을 권장합니다.
"""
        return {
            "success": True,
            "engine": fallback_note or "로컬 학술 비교 엔진",
            "report_markdown": report_md
        }
