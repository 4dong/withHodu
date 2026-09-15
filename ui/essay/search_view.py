"""
Search View: Hybrid keyword/vector retrieval and grounded RAG question answering.
"""

from __future__ import annotations
import streamlit as st
from ui.hodu import page_header, show_state, loading, state_html
from typing import Optional, Dict, Any

from core.essay.repository import EssayRepository
from core.essay.retrieval import EssaySearchEngine
from core.essay.embedding import get_active_embedding_provider, MockEmbeddingProvider, GeminiEmbeddingProvider
from core.essay.rag import EssayRAGService, MockRAGGenerator, GeminiRAGGenerator
from core.key_manager import KeyManager


def render_essay_search_view(repo: EssayRepository):
    page_header('근거 검색', '승인한 자소서에서 문단을 찾고, 출처가 붙은 답변을 보여 줘요.')

    # Unified Active Embedding Provider & RAG Generator (F06)
    embed_provider = get_active_embedding_provider()
    key, _ = KeyManager.get_active_key()
    has_key = bool(key)

    if has_key:
        rag_gen = GeminiRAGGenerator(api_key=key)
    else:
        rag_gen = MockRAGGenerator()

    search_engine = EssaySearchEngine(repo, embedding_provider=embed_provider)
    rag_svc = EssayRAGService(repo, search_engine, generator=rag_gen)

    # Search Bar
    col_q, col_btn = st.columns([4, 1])
    with col_q:
        user_query = st.text_input(
            "검색어 또는 질문 입력",
            placeholder="예: 해외 현장에서 로그 수집해 제어기 분석한 사례, CANalyzer FRAM, PV5 지원동기",
            label_visibility="collapsed"
        )
    with col_btn:
        run_search = st.button("검색", type="primary", use_container_width=True)

    # Filters
    with st.expander("검색 범위"):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            all_docs = repo.list_documents(include_deleted=False)
            companies = sorted(list({d.company for d in all_docs if d.company}))
            comp_filter = st.selectbox("기업", options=["전체"] + companies, key="essay_search_company")
        with col_f2:
            col_filter = st.selectbox(
                "자료 구분",
                key="essay_search_collection",
                options=["전체", "reference", "own_draft", "own_experience"],
                format_func=lambda x: {
                    "전체": "전체",
                    "reference": "참고 자소서만",
                    "own_draft": "내 초안만",
                    "own_experience": "내 경험만"
                }.get(x, x)
            )

    q = user_query.strip()
    if run_search and not q:
        st.info("찾고 싶은 경험이나 질문을 입력해 주세요.")
    cache_key = f"{q}:{comp_filter}:{col_filter}"

    # F10: Avoid duplicate search on widget reruns by caching results in session_state
    if q and (run_search or ("essay_search_results" not in st.session_state and "essay_last_search_query" in st.session_state)):
        st.session_state["essay_last_search_query"] = q
        filters: Dict[str, Any] = {}
        if comp_filter != "전체":
            filters["company"] = comp_filter
        if col_filter != "전체":
            filters["collection"] = col_filter

        with loading("근거를 찾고 있어요", "", "search"):
            grounded_answer = rag_svc.answer_question(q, filters=filters, max_evidence=5)
            search_response = search_engine.search(q, filters=filters, limit=5)
            st.session_state["essay_search_results"] = (grounded_answer, search_response)
            st.session_state["essay_current_cache_key"] = cache_key

    if "essay_search_results" not in st.session_state:
        show_state("검색어나 질문을 입력해 주세요", "", "search", "empty")

    if "essay_search_results" in st.session_state and st.session_state.get("essay_last_search_query"):
        grounded_answer, search_response = st.session_state["essay_search_results"]

        # 1. Grounded RAG Answer Box
        with st.container(border=True, key="card_essay_answer"):
            col_h1, col_h2 = st.columns([3.5, 1.5])
            with col_h1:
                st.markdown("#### 답변")
            with col_h2:
                mode_badge = "Gemini 답변" if has_key else "오프라인 답변"
                st.caption(mode_badge)

            if grounded_answer.status == "answered":
                st.markdown(grounded_answer.answer)
            elif grounded_answer.status == "insufficient_evidence":
                st.warning(f"**근거 부족**: {grounded_answer.answer}")
            else:
                st.error("답변 생성 중 오류가 발생했습니다.")

            if grounded_answer.citations:
                st.markdown("##### 출처")
                for cit in grounded_answer.citations:
                    rev = repo.get_revision(cit.revision_id)
                    ans = repo.get_answer(cit.answer_id) if rev else None
                    doc = repo.get_document(ans.document_id) if ans else None
                    doc_title = doc.title if doc else "자소서 문서"
                    st.info(f"**[{cit.id}] {doc_title} (문항 {ans.question_number if ans else 1})**\n\n*인용구*: \"{cit.quote}\"")

            if grounded_answer.limitations:
                st.markdown("##### 유의사항")
                for lim in grounded_answer.limitations:
                    st.caption(f"• {lim}")

        # 2. Search Evidence Hits
        st.markdown(f"#### 관련 문단 ({search_response.total_hits}건)")
        for idx, hit in enumerate(search_response.hits):
            with st.container(border=True, key=f"card_essay_hit_{idx}"):
                st.markdown(f"**#{idx+1}. [{hit.company}] {hit.document_title} - 문항 {hit.question_number}** ({hit.match_origin})")
                st.caption(f"질문: {hit.question_text}")
                st.markdown(f"> {hit.text}")
                st.caption(f"관련도 {hit.score:.4f} · {hit.collection}", help="검색 방식별 순위를 합친 RRF 점수입니다.")
