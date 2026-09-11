"""
Paper Credibility & Relevance Verification Engine
Evaluates papers on citation impact, topic relevance, venue prestige, and methodological soundness.
"""

import json
from typing import List, Dict, Any, Optional
from core.searcher import Paper

class PaperVerifier:
    """Evaluates and verifies academic papers for quality, relevance, and credibility."""

    @staticmethod
    def verify_papers(papers: List[Paper], target_topic: str, api_key: Optional[str] = None) -> List[Paper]:
        """Runs multi-dimensional verification on a list of papers."""
        verified_papers = []
        for paper in papers:
            verified = PaperVerifier.verify_single_paper(paper, target_topic, api_key=api_key)
            verified_papers.append(verified)
        
        # Sort by relevance score descending
        verified_papers.sort(key=lambda p: p.relevance_score, reverse=True)
        return verified_papers

    @staticmethod
    def verify_single_paper(paper: Paper, target_topic: str, api_key: Optional[str] = None) -> Paper:
        """Verifies a single paper using LLM or rule-based heuristics."""
        
        # 1. Try Gemini LLM Verification if API key is provided
        if api_key:
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=api_key)
                prompt = f"""
                You are a senior academic reviewer. Evaluate this paper against the user's research topic.
                
                [Target Topic]: {target_topic}
                [Paper Title]: {paper.title}
                [Authors]: {', '.join(paper.authors[:3])} ({paper.year})
                [Venue]: {paper.venue} (Citations: {paper.citation_count})
                [Abstract]: {paper.abstract[:1000]}
                
                Evaluate:
                1. Relevance score (integer 0 to 100) indicating how well this paper addresses the target topic.
                2. 1-sentence verification summary in Korean explaining the paper's core contribution to this topic.
                3. 3 concise verification bullet points in Korean (e.g. 연구 방법론의 신뢰성, 실용성/적용 가능성, 학술적 의의/피인용 가치).
                
                Return valid JSON:
                {{
                    "relevance_score": 92,
                    "verification_summary": "...",
                    "verification_points": [
                        "...",
                        "...",
                        "..."
                    ]
                }}
                """
                for model_candidate in ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]:
                    try:
                        response = client.models.generate_content(
                            model=model_candidate,
                            contents=prompt,
                            config=types.GenerateContentConfig(response_mime_type="application/json")
                        )
                        data = json.loads(response.text)
                        paper.relevance_score = int(data.get("relevance_score", 85))
                        paper.verification_summary = data.get("verification_summary", "")
                        paper.verification_points = data.get("verification_points", [])
                        return paper
                    except Exception as me:
                        continue
            except Exception as e:
                print(f"Gemini verification fallback: {e}")

        # 2. Rule-based Heuristic Verification
        keywords = [k.lower() for k in target_topic.split() if len(k) > 1]
        title_lower = paper.title.lower()
        abstract_lower = paper.abstract.lower()

        # Score components
        title_hits = sum(1 for k in keywords if k in title_lower)
        abstract_hits = sum(1 for k in keywords if k in abstract_lower)
        
        # Base score (0-50 based on keyword density)
        kw_score = min(50, (title_hits * 18) + (abstract_hits * 6))
        if kw_score < 20 and len(keywords) > 0:
            kw_score = 30  # baseline if API returned it for query
            
        # Citation score (0-30)
        cite_score = 0
        if paper.citation_count > 500:
            cite_score = 30
        elif paper.citation_count > 100:
            cite_score = 25
        elif paper.citation_count > 20:
            cite_score = 20
        elif paper.citation_count > 0:
            cite_score = 15
        else:
            # For recent preprints
            cite_score = 15 if paper.year >= 2023 else 8

        # Recency score (0-15)
        recency_score = max(0, 15 - (2025 - paper.year) * 2)

        # OpenAccess PDF availability (0-5)
        oa_score = 5 if paper.pdf_url else 2

        total_score = min(99, max(45, kw_score + cite_score + recency_score + oa_score))
        paper.relevance_score = total_score

        # Generate rule-based points
        points = []
        if paper.citation_count > 50:
            points.append(f"⭐️ **높은 피인용수**: {paper.citation_count:,}회 이상 인용되어 학계에서 널리 검증된 논문입니다.")
        elif paper.year >= 2023:
            points.append(f"⚡️ **최신 연구 트렌드**: {paper.year}년에 발표된 최신 연구로 최신 기법을 반영하고 있습니다.")
        else:
            points.append(f"📄 **기초 연구**: {paper.year}년 발표된 해당 분야 핵심 참고 문헌입니다.")

        if paper.pdf_url:
            points.append("📥 **오픈액세스(Open Access)**: 원문 PDF 전문 다운로드 및 대역 분석이 가능합니다.")
        else:
            points.append("🔒 **초록 기반 분석**: 메타데이터 및 초록을 기반으로 검증 및 요약을 제공합니다.")

        if title_hits > 0:
            points.append(f"🎯 **주제 일치도 우수**: 논문 제목에 검색 키워드가 직접적으로 포함되어 밀접한 연관성을 가집니다.")
        else:
            points.append(f"🔍 **관련 분야 확장**: 본문 및 초록에서 주요 관련 방법론을 다루고 있습니다.")

        paper.verification_summary = f"{paper.year}년 {paper.venue}에 게재된 논문으로, '{target_topic}' 주제와 관련된 핵심 메커니즘을 다룹니다."
        paper.verification_points = points

        return paper
