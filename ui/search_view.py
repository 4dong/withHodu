"""Paper search page: the query form, results, and Gemini's query refiner."""

from typing import Any, Dict

import streamlit as st

from core.downloader import ArchiveManager
from core.intent_copilot import IntentCopilotAgent
from core.searcher import AcademicSearcher
from ui.hodu import loading, page_header, show_state
from ui.reader import process_paper_and_load


def trigger_search_flow(search_query: str, sidebar_config: Dict[str, Any]):
    """Searches Google Scholar, then arXiv and Semantic Scholar, behind the walking-Hodu loading state."""
    st.session_state["hodu_search_error"] = None
    try:
        with loading("논문을 찾고 있어요", search_query, "search"):
            searcher = AcademicSearcher()
            raw_papers = searcher.search(query=search_query, max_results=sidebar_config.get("max_results", 5))
    except Exception:
        st.session_state["hodu_search_error"] = "잠시 후 다시 검색해 주세요. 이전 결과는 그대로 있어요."
        return
    st.session_state.current_topic = search_query
    st.session_state.search_results = raw_papers or []
    if raw_papers:
        st.session_state.current_paper_bundle = None
        st.session_state.page_translations = {}
        st.session_state.current_page_num = 1


def render_search_page(archive_mgr: ArchiveManager, sidebar_config: Dict[str, Any]):
    page_header("논문 검색")

    with st.form("main_paper_search"):
        col_query, col_submit = st.columns([5, 1], vertical_alignment="bottom")
        with col_query:
            query = st.text_input("주제, 키워드 또는 논문 제목", placeholder="예: 음성 합성, 검색 증강 생성", key="hodu_paper_query")
        with col_submit:
            submitted = st.form_submit_button("검색", type="primary", use_container_width=True, icon=":material/search:")
    if submitted:
        if query.strip():
            trigger_search_flow(query.strip(), sidebar_config)
            st.rerun()
        else:
            st.info("검색어를 입력해 주세요.")
    if st.session_state.get("hodu_search_error"):
        show_state("논문을 찾는 도중 연결이 끊겼어요", st.session_state["hodu_search_error"], "think", "error")
    if st.session_state.search_results:
        render_search_results_view(archive_mgr, sidebar_config)
    elif not st.session_state.get("hodu_search_error"):
        if st.session_state.get("current_topic"):
            show_state("찾은 논문이 없어요", "다른 검색어로 찾아보세요.", "think", "empty")
        else:
            show_state("열어 본 논문은 나의 서재에 자동으로 보관돼요", "", "fetch", "empty")


def render_search_results_view(archive_mgr: ArchiveManager, sidebar_config: Dict[str, Any]):
    """Displays clean search results with an ultra-minimalist Apple Spotlight AI Re-search bar."""
    topic = st.session_state.current_topic
    papers = st.session_state.search_results

    with st.container(border=True, key="card_refine"):
        st.markdown('<p class="h-card-label">Gemini로 검색어 다듬기</p>', unsafe_allow_html=True)

        # Single Clean Apple Spotlight Input Capsule
        col_inp, col_send = st.columns([3.8, 1.2])
        with col_inp:
            copilot_query_input = st.text_input(
                "찾고 싶은 연구 설명",
                placeholder="예: CosyVoice 3의 제로샷 음성 복제 기술이나 latency 줄이는 최신 논문 찾아줘",
                key="copilot_user_input",
                label_visibility="collapsed"
            )
        with col_send:
            if st.button("다시 검색", key="btn_run_copilot", type="primary", use_container_width=True):
                if copilot_query_input.strip():
                    with loading("검색어를 다듬고 있어요", "", "think"):
                        analysis_res = IntentCopilotAgent.analyze_intent_and_suggest_queries(
                            current_query=topic,
                            user_message=copilot_query_input.strip(),
                            retrieved_papers=papers,
                            model_choice="🤖 Google Gemini 3.5 Flash",
                            api_key=sidebar_config.get("api_key")
                        )
                        suggs = analysis_res.get("suggested_queries", [])
                        if suggs:
                            best_q = suggs[0].get("query", copilot_query_input.strip())
                            st.session_state["copilot_latest_suggestions"] = suggs[1:5]
                            trigger_search_flow(best_q, sidebar_config)
                            st.rerun()

        # Optional Clean Single-Row Alternate Keyword Quick-Pills
        latest_suggs = st.session_state.get("copilot_latest_suggestions", [])
        if latest_suggs:
            q_cols = st.columns(min(len(latest_suggs), 4))
            for s_idx, sugg in enumerate(latest_suggs[:4]):
                with q_cols[s_idx]:
                    q_label = sugg.get("label", f"키워드 {s_idx+1}")
                    q_str = sugg.get("query", "")
                    q_reason = sugg.get("reason", "")
                    if st.button(f"{q_label}", key=f"btn_alt_sugg_{s_idx}", help=f"'{q_str}'(으)로 다시 검색\n- {q_reason}", use_container_width=True):
                        st.session_state["copilot_latest_suggestions"] = []
                        trigger_search_flow(q_str, sidebar_config)
                        st.rerun()

    st.subheader(f"'{topic}' 검색 결과 ({len(papers)}건)")

    for idx, paper in enumerate(papers):
        with st.container(border=True, key=f"card_result_{idx}"):
            col_info, col_btn = st.columns([4, 1.4])
            with col_info:
                cite_str = f"인용 {paper.citation_count}회" if paper.citation_count and paper.citation_count > 0 else "최신 논문"
                st.markdown(f"### #{paper.rank} {paper.title}")
                date_str = paper.get_formatted_date()
                safe_authors = (paper.authors or [])[:3]
                st.caption(f"**저자**: {', '.join(safe_authors)} · **발행일**: {date_str} · **출처**: {paper.venue} · **{cite_str}**")
                st.write((paper.abstract or "")[:250] + "...")
            with col_btn:
                if st.button("번역해서 보기", key=f"open_btn_{idx}", type="primary", use_container_width=True):
                    process_paper_and_load(
                        paper, topic, archive_mgr,
                        api_key=sidebar_config.get("api_key"),
                        engine=sidebar_config.get("selected_engine", "⚡️ Google Neural (고속 0.3초 · 무료)"),
                        custom_prompt=sidebar_config.get("custom_prompt")
                    )
                if paper.url:
                    st.link_button("원문 링크", paper.url, use_container_width=True)
