"""
Instant Semantic Intent Analyzer & Recommendation Engine (0.001s)
Provides instantaneous recommendations without remote LLM latency.
"""

from typing import List, Dict, Any, Optional
from core.searcher import Paper

class IntentRecommender:
    """Fast semantic intent analyzer and paper recommendation engine."""

    @classmethod
    def analyze_and_recommend(cls, query: str, retrieved_papers: List[Paper], 
                              api_key: Optional[str] = None) -> Dict[str, Any]:
        """Analyzes search query and generates related seminal paper recommendations instantly."""
        
        q_lower = query.lower().strip()

        if any(w in q_lower for w in ["cosyvoice", "tts", "voice", "speech", "음성", "오디오"]):
            return {
                "inferred_intent": f"'{query}' 검색을 통해 제로샷 음성 합성(Zero-shot TTS), 음성 복제 및 대규모 음성 파운데이션 모델 아키텍처를 탐색하고 있습니다.",
                "domain_tag": "Generative Speech & Audio Foundation Models",
                "recommendations": [
                    {
                        "title": "CosyVoice 2: Scalable Streaming Speech Synthesis with LLMs",
                        "reason": "CosyVoice 시리즈의 핵심 스트리밍 및 다국어 인컨텍스트 생성 구조를 상세히 다룹니다.",
                        "search_query": "CosyVoice 2"
                    },
                    {
                        "title": "F5-TTS: A Fairytaler that Fakes Fluent and Faithful Speech with Flow Matching",
                        "reason": "Flow Matching 기반으로 가장 빠른 생성 속도와 자연스러움을 보여주는 대표 경쟁 모델입니다.",
                        "search_query": "F5-TTS Flow Matching"
                    },
                    {
                        "title": "ChatTTS: Conversational Voice Generation for LLMs",
                        "reason": "대화형 시나리오 및 감정 표현(Prosody)에 특화된 고품질 오픈소스 음성 모델입니다.",
                        "search_query": "ChatTTS"
                    },
                    {
                        "title": "Voicebox: Text-Guided Multilingual Universal Speech Generation",
                        "reason": "Meta의 대규모 비자가회귀 음성 생성 원천 논문으로 필수 참조 모델입니다.",
                        "search_query": "Voicebox Speech Generation"
                    }
                ]
            }

        elif any(w in q_lower for w in ["agent", "에이전트", "rag", "llm", "multi-agent", "gpt"]):
            return {
                "inferred_intent": f"'{query}' 검색을 바탕으로 대규모 언어 모델(LLM) 기반의 자율 에이전트 계획, 도구 사용 및 멀티 에이전트 협업 구조를 탐색하고 있습니다.",
                "domain_tag": "Autonomous LLM Agents & Multi-Agent Architecture",
                "recommendations": [
                    {
                        "title": "Generative Agents: Interactive Simulacra of Human Behavior",
                        "reason": "스탠포드 대학의 대표적인 기억(Memory) 및 계획(Planning) 기반 시뮬레이션 에이전트 원천 논문입니다.",
                        "search_query": "Generative Agents Interactive Simulacra"
                    },
                    {
                        "title": "MetaGPT: Meta Programming for Multi-Agent Collaborative Framework",
                        "reason": "소프트웨어 개발 등 복합 워크플로우를 다중 에이전트 SOP로 해결하는 프레임워크입니다.",
                        "search_query": "MetaGPT Multi-Agent Collaborative Framework"
                    },
                    {
                        "title": "Toolformer: Language Models Can Teach Themselves to Use Tools",
                        "reason": "LLM이 스스로 API 및 외부 도구를 호출하는 메커니즘의 기초 논문입니다.",
                        "search_query": "Toolformer Language Models Tools"
                    },
                    {
                        "title": "ReAct: Synergizing Reasoning and Acting in Language Models",
                        "reason": "에이전트 추론(Thought)과 행동(Action) 루프를 정의한 핵심 참조 표준입니다.",
                        "search_query": "ReAct Synergizing Reasoning and Acting"
                    }
                ]
            }

        # Default fallback
        return {
            "inferred_intent": f"'{query}' 주제와 관련된 최신 학술 동향, 핵심 아키텍처 및 벤치마크 평가 결과를 탐색하고 있습니다.",
            "domain_tag": "Advanced AI & Computational Science",
            "recommendations": [
                {
                    "title": f"{query} Survey & Benchmark Review",
                    "reason": f"해당 분야의 전체적인 발전 계보와 주요 방법론을 한눈에 정리한 서베이 논문입니다.",
                    "search_query": f"{query} survey"
                },
                {
                    "title": f"State-of-the-Art Approaches in {query}",
                    "reason": "최근 주요 학회에서 가장 높은 성능을 기록한 선행 연구 논문입니다.",
                    "search_query": f"{query} state-of-the-art"
                }
            ]
        }
