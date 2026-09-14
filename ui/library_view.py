"""
Apple Store Design System: Ultra-Minimalist Canvas (#F5F5F7), Pure White Cards (#FFFFFF),
Dark Featured Card (#000000), Massive Typography & Seamless Floating Product Presentation.
"""

import os
import re
import html as html_mod
import shutil
import streamlit as st
from typing import Dict, Any, List, Optional
from core.downloader import ArchiveManager
from core.searcher import Paper
from core.analyzer import MultiPaperComparativeAgent
from ui.sidebar import engine_label
from ui.hodu import page_header, section_intro, show_state, loading
from core.translator import PaperTranslator
from core.parser import PaperPDFParser
from core.key_manager import KeyManager

def render_library_view(archive_mgr: ArchiveManager, sidebar_config: Dict[str, Any]):
    """Renders the Apple Store-inspired ultra-minimalist academic library hub."""

    # 1. State Management
    if "goodnotes_active_folder" not in st.session_state:
        st.session_state["goodnotes_active_folder"] = None

    if "selected_library_paper_paths" not in st.session_state:
        st.session_state["selected_library_paper_paths"] = []

    all_papers = archive_mgr.get_all_archived_papers()
    topics = archive_mgr.list_archived_topics()
    reports = archive_mgr.list_comparison_reports()
    active_folder = st.session_state.get("goodnotes_active_folder")

    # -------------------------------------------------------------
    # 🍎 2. Apple Store Hero Section (Massive Bold 36px Title)
    # -------------------------------------------------------------
    if active_folder == "_reports":
        page_header("비교분석 보고서", "함께 읽은 논문들의 공통점과 차이를 모아두었어요.", "read", "호두랑 · 나의 서재")
    elif active_folder:
        page_header(f"{active_folder} 서재", f"이 주제로 모아 둔 논문 {len(archive_mgr.list_papers_in_topic(active_folder))}편을 꺼내 읽어요.", "organize", "호두랑 · 나의 서재")
    else:
        page_header("나의 서재", "호두와 모아 둔 논문을 다시 펼쳐요. 비교한 내용도 여기에서 만나요.", "read", "호두랑 · 읽고 모으기")

    with st.container(key="library_toolbar"):
        summary, action = st.columns([3, 1.2], vertical_alignment="center")
        with summary:
            st.markdown(f'<div class="h-library-summary"><strong>{len(all_papers)}</strong>편의 논문'
                        f'<span>컬렉션 {len(topics)}개 · 보고서 {len(reports)}건</span></div>', unsafe_allow_html=True)
        with action, st.popover("새 컬렉션", icon=":material/add:", use_container_width=True):
            st.markdown("##### 새 컬렉션 만들기")
            new_col_name = st.text_input("폴더 이름", placeholder="예: Diffusion Models", label_visibility="collapsed")
            if st.button("생성하기", key="btn_create_new_topic", type="primary", use_container_width=True) and new_col_name.strip():
                new_topic_dir = os.path.join(archive_mgr.base_dir, archive_mgr._sanitize_folder_name(new_col_name.strip()))
                os.makedirs(new_topic_dir, exist_ok=True)
                st.session_state["goodnotes_active_folder"] = new_col_name.strip()
                st.success("새 컬렉션이 생성되었습니다.")
                st.rerun()

    # Back to Storefront Button
    if active_folder:
        if st.button("‹ 서재 전체로 돌아가기", use_container_width=False):
            st.session_state["goodnotes_active_folder"] = None
            st.rerun()

    # 3. Mode Navigation Tabs
    tab_shelf, tab_all_root, tab_agent = st.tabs([
        "컬렉션",
        "전체 논문",
        "비교분석"
    ])

    # ----------------------------------------------------------------------------------
    # TAB 1: 🍎 컬렉션 (Apple Store Layout)
    # ----------------------------------------------------------------------------------
    with tab_shelf:
        if not active_folder:
            # Display any folder deletion alert message if set
            if st.session_state.get("folder_delete_error"):
                st.error(st.session_state["folder_delete_error"])
                st.session_state["folder_delete_error"] = None
            if st.session_state.get("folder_delete_success"):
                st.success(st.session_state["folder_delete_success"])
                st.session_state["folder_delete_success"] = None

            # ----------------------------------------------------------------------
            # 🏛️ Apple Store Symmetrical Layout:
            # [Left: Dark Featured Card #000000] | [Right: White Product Cards #FFFFFF]
            # ----------------------------------------------------------------------
            col_white_grid, col_dark_featured = st.columns([2.85, 1.15])

            # 🖤 LEFT: High-Contrast Dark Featured Card (#000000)
            with col_dark_featured, st.container(key="library_reports_card"):
                st.markdown(
                    f'<div class="h-report-intro"><span class="apple-store-eyebrow">분석 보고서</span>'
                    f'<h3>논문 사이의 연결을<br>발견해 보세요.</h3>'
                    f'<p>여러 논문을 비교한 결과를<br>한곳에서 꺼내 볼 수 있어요.</p>'
                    f'<span class="ap-badge">보고서 {len(reports)}건</span></div>',
                    unsafe_allow_html=True,
                )
                if st.button("보고서 보관함 열기", key="btn_open_reports_vault", type="secondary", use_container_width=True):
                    st.session_state["goodnotes_active_folder"] = "_reports"
                    st.rerun()

            # 🤍 RIGHT: Apple Store White Collection Cards Grid (#FFFFFF)
            with col_white_grid:
                st.markdown(
                    f"""
                    <div style="display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 0.8rem;">
                        <span style="font-size: 1.35rem; font-weight: 800; color: #39392E; letter-spacing: -0.02em;">연구 주제 컬렉션</span>
                        <span style="font-size: 0.88rem; color: #747366; font-weight: 600;">{len(topics)}개 컬렉션</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if not topics:
                    show_state("첫 논문을 모아볼까요?", "논문 검색에서 논문을 열면 주제별 컬렉션에 자동으로 보관해요.", "organize", "empty")
                else:
                    cols_per_row = 2
                    for r_idx in range(0, len(topics), cols_per_row):
                        row_topics = topics[r_idx:r_idx + cols_per_row]
                        f_cols = st.columns(cols_per_row)

                        for c_idx, t in enumerate(row_topics):
                            with f_cols[c_idx]:
                                t_papers = archive_mgr.list_papers_in_topic(t)

                                # Pure White Borderless Card (#FFFFFF) with Soft Elevation
                                with st.container(border=True, key=f"library_collection_{r_idx}_{c_idx}"):
                                    col_f_name, col_f_del = st.columns([4, 1])
                                    with col_f_name:
                                        st.markdown(
                                            f"""
                                            <span class="apple-store-eyebrow" style="color: #747366; font-size: 0.72rem; margin-bottom: 0.1rem;">컬렉션</span>
                                            <div class="apple-product-topic-name" title="{html_mod.escape(str(t))}">{html_mod.escape(str(t))}</div>
                                            """,
                                            unsafe_allow_html=True
                                        )
                                    with col_f_del:
                                        if st.button("삭제", icon=":material/delete:", type="tertiary", key=f"del_topic_{t}_{r_idx}_{c_idx}", help=f"'{t}' 빈 컬렉션 삭제"):
                                            if len(t_papers) > 0:
                                                st.session_state["folder_delete_error"] = f"'{t}'에 논문 {len(t_papers)}편이 있어 삭제할 수 없습니다. 논문을 다른 컬렉션으로 옮기거나 삭제한 뒤 다시 시도해 주세요."
                                            else:
                                                topic_dir = os.path.join(archive_mgr.base_dir, t)
                                                if os.path.exists(topic_dir):
                                                    shutil.rmtree(topic_dir, ignore_errors=True)
                                                st.session_state["folder_delete_success"] = f"'{t}' 컬렉션을 삭제했습니다."
                                            st.rerun()

                                    st.markdown(f"<div class='apple-product-price-tag'>보관된 학술 논문 {len(t_papers)}편</div>", unsafe_allow_html=True)

                                    if st.button(f"컬렉션 열기 ›", key=f"btn_open_f_{t}_{r_idx}_{c_idx}", type="secondary", use_container_width=True):
                                        st.session_state["goodnotes_active_folder"] = t
                                        st.rerun()

            st.markdown("<div style='margin-top: 2.5rem;'></div>", unsafe_allow_html=True)

            # -------------------------------------------------------------
            # 🌟 3. Apple Store Product Carousel / Bookshelf Presentation
            # -------------------------------------------------------------
            st.markdown(
                """
                <div style="margin-bottom: 1.2rem;">
                    <span class="apple-store-eyebrow">최근에 모은 논문</span>
                    <div style="font-size: 1.6rem; font-weight: 800; color: #39392E; letter-spacing: -0.025em;">최근 연구 논문 서재</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            _render_bookshelf_grid(all_papers[:8], archive_mgr, topics, prefix="rec_shelf", sidebar_config=sidebar_config)

        elif active_folder == "_reports":
            # ------------------------------------------------------------------------------
            # Dedicated Reports Folder View (📑 AI 분석 보고서 모아보기)
            # ------------------------------------------------------------------------------
            if not reports:
                st.info("아직 작성된 AI 비교분석 보고서가 없습니다. '비교분석' 탭에서 논문들을 선택하여 분석을 시작해보세요.")
            else:
                for idx, r_meta in enumerate(reports):
                    r_id = r_meta.get("id")
                    with st.container(border=True):
                        col_r_icon, col_r_info, col_r_actions = st.columns([0.6, 3.4, 1.8])
                        with col_r_icon:
                            st.markdown("<div style='font-size: 0.75rem; font-weight: 700; color: #3F5947; text-align: center; padding-top: 0.6rem;'>보고서</div>", unsafe_allow_html=True)
                        with col_r_info:
                            st.markdown(f"#### {r_meta.get('title')}")
                            st.caption(f"{r_meta.get('created_at')} · {r_meta.get('engine')} · 논문 {r_meta.get('paper_count')}편")
                            st.write(f"**비교 대상 논문**: {', '.join(r_meta.get('papers', []))}")
                        with col_r_actions:
                            full_rep = archive_mgr.get_comparison_report(r_id)
                            report_md_text = full_rep.get("markdown", "") if full_rep else ""

                            with st.popover("보고서 보기", use_container_width=True, key=f"view_rep_card_{r_id}_{idx}"):
                                if full_rep:
                                    st.markdown(full_rep.get("markdown"), unsafe_allow_html=True)

                            st.download_button(
                                "Markdown 다운로드",
                                data=report_md_text,
                                file_name=f"{r_meta.get('title')[:30]}.md",
                                mime="text/markdown",
                                key=f"dl_rep_btn_{r_id}_{idx}",
                                use_container_width=True
                            )

                            with st.popover("삭제", icon=":material/delete:", use_container_width=True, key=f"del_rep_card_pop_{r_id}_{idx}"):
                                st.caption("이 보고서를 삭제합니다. 되돌릴 수 없습니다.")
                                if st.button("보고서 삭제", key=f"del_rep_card_{r_id}_{idx}", type="primary", use_container_width=True):
                                    archive_mgr.delete_comparison_report(r_id)
                                    st.rerun()

        else:
            # ------------------------------------------------------------------------------
            # Inside a specific topic folder: Render all papers in this folder
            # ------------------------------------------------------------------------------
            folder_papers = archive_mgr.list_papers_in_topic(active_folder)

            col_f_header, col_f_batch_move, col_f_batch_del = st.columns([2.5, 1.3, 1.2])
            with col_f_header:
                st.markdown(f"### {active_folder} ({len(folder_papers)}편)")

            # Folder-level Batch Actions
            if folder_papers:
                with col_f_batch_move:
                    with st.popover("전체 이동", icon=":material/drive_file_move:", use_container_width=True):
                        st.markdown("**모든 논문을 다른 컬렉션으로 이동**")
                        target_new_t = st.text_input("컬렉션 이름", placeholder="이동할 컬렉션 이름", key=f"batch_mv_input_{active_folder}")
                        if st.button("이동하기", key=f"batch_mv_exec_{active_folder}", type="primary", use_container_width=True) and target_new_t.strip():
                            for fp in folder_papers:
                                archive_mgr.move_paper_topic(fp.get("folder_path"), target_new_t.strip())
                            st.session_state["goodnotes_active_folder"] = target_new_t.strip()
                            st.success("이동했습니다.")
                            st.rerun()

                with col_f_batch_del:
                    with st.popover("컬렉션 삭제", icon=":material/delete:", use_container_width=True):
                        st.warning(f"논문 {len(folder_papers)}편과 컬렉션이 함께 삭제됩니다. 되돌릴 수 없습니다.")
                        if st.button("컬렉션 삭제", key=f"del_entire_folder_{active_folder}", type="primary", use_container_width=True):
                            topic_dir = os.path.join(archive_mgr.base_dir, active_folder)
                            archive_mgr.delete_paper(topic_dir)
                            st.session_state["goodnotes_active_folder"] = None
                            st.rerun()

            if not folder_papers:
                st.info("이 컬렉션에 논문이 없습니다. 다른 컬렉션의 논문을 옮기거나 새 논문을 검색해 추가하세요.")
            else:
                _render_bookshelf_grid(folder_papers, archive_mgr, topics, prefix=f"f_{active_folder}", sidebar_config=sidebar_config)

    # ----------------------------------------------------------------------------------
    # TAB 2: 🌐 전체 논문
    # ----------------------------------------------------------------------------------
    with tab_all_root:
        st.markdown(
            """
            <div style="margin-bottom: 1.2rem;">
                <span class="apple-store-eyebrow">모든 논문</span>
                <div style="font-size: 1.8rem; font-weight: 800; color: #39392E; letter-spacing: -0.025em;">전체 논문</div>
                <div style="font-size: 1rem; color: #747366;">보관한 모든 논문을 찾고, 이름을 바꾸거나 옮기고, 비교분석할 논문을 고릅니다.</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if not all_papers:
            show_state("아직 서재가 비어 있어요", "논문 검색에서 첫 논문을 골라 주세요. 호두가 잘 모아둘게요.", "rest", "empty")
        else:
            # Filter bar
            col_s_q, col_s_t, col_s_sort = st.columns([2.5, 1.3, 1.2])
            with col_s_q:
                filter_q = st.text_input("제목·저자·키워드로 찾기", placeholder="검색어 입력...", key="root_filter_q", label_visibility="collapsed")
            with col_s_t:
                topic_f = st.selectbox("폴더 필터", ["전체"] + topics, key="root_topic_f", label_visibility="collapsed")
            with col_s_sort:
                sort_f = st.selectbox("정렬", ["최신 등록순", "연도순", "제목순"], key="root_sort_f", label_visibility="collapsed")

            filtered = all_papers
            if filter_q.strip():
                cq = filter_q.strip().lower()
                filtered = [p for p in filtered if cq in (p.get("title") or "").lower() or any(cq in a.lower() for a in (p.get("authors") or []))]
            if topic_f != "전체":
                filtered = [p for p in filtered if p.get("topic") == topic_f]

            if sort_f == "최신 등록순":
                filtered = sorted(filtered, key=lambda x: x.get("updated_at", ""), reverse=True)
            elif sort_f == "연도순":
                filtered = sorted(filtered, key=lambda x: x.get("year", 0), reverse=True)
            elif sort_f == "제목순":
                filtered = sorted(filtered, key=lambda x: (x.get("title") or "").lower())

            # Batch Selection Bar
            sel_count = len(st.session_state["selected_library_paper_paths"])
            col_b_info, col_b_run, col_b_move, col_b_del = st.columns([2.5, 1.8, 1.5, 1.2])
            with col_b_info:
                st.markdown(f"**선택된 논문**: `{sel_count}편`")
            with col_b_run:
                if st.button("선택한 논문 비교분석", key="btn_batch_comp_root", disabled=(sel_count < 2), type="primary", use_container_width=True):
                    st.session_state["active_library_tab"] = "agent"
                    st.rerun()
            with col_b_move:
                with st.popover("선택 이동", icon=":material/drive_file_move:", disabled=(sel_count == 0), use_container_width=True):
                    dest_t = st.text_input("이동할 컬렉션", placeholder="예: Speech AI", key="dest_batch_t_input")
                    if st.button("이동 실행", key="btn_batch_move_exec", type="primary", use_container_width=True) and dest_t.strip():
                        for p_path in st.session_state["selected_library_paper_paths"]:
                            archive_mgr.move_paper_topic(p_path, dest_t.strip())
                        st.session_state["selected_library_paper_paths"] = []
                        st.success("이동했습니다.")
                        st.rerun()
            with col_b_del:
                with st.popover("선택 삭제", icon=":material/delete:", disabled=(sel_count == 0), use_container_width=True):
                    st.warning(f"선택한 논문 {sel_count}편을 삭제합니다. 되돌릴 수 없습니다.")
                    if st.button("삭제하기", key="btn_batch_del_root", type="primary", use_container_width=True):
                        for p_path in st.session_state["selected_library_paper_paths"]:
                            archive_mgr.delete_paper(p_path)
                        st.session_state["selected_library_paper_paths"] = []
                        st.rerun()

            # Render Full Bookshelf Grid
            _render_bookshelf_grid(filtered, archive_mgr, topics, prefix="root_all", sidebar_config=sidebar_config)

    # ----------------------------------------------------------------------------------
    # TAB 3: 🤖 비교분석
    # ----------------------------------------------------------------------------------
    with tab_agent:
        st.markdown(
            """
            <div style="margin-bottom: 1.2rem;">
                <span class="apple-store-eyebrow">LABORATORY</span>
                <div style="font-size: 1.8rem; font-weight: 800; color: #39392E; letter-spacing: -0.025em;">논문 비교분석</div>
                <div style="font-size: 1rem; color: #747366;">선택한 논문의 구조, 평가 지표, 학습 방식을 비교한 보고서를 만듭니다.</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        sub_tab_new, sub_tab_history = st.tabs(["새 비교분석", f"저장된 보고서 ({len(reports)}건)"])

        with sub_tab_new:
            all_paper_dict = {f"{p.get('title')} ({p.get('year')}년 / {p.get('topic')})": p for p in all_papers}

            default_selected_titles = []
            for name, p_data in all_paper_dict.items():
                if p_data.get("folder_path") in st.session_state.get("selected_library_paper_paths", []):
                    default_selected_titles.append(name)

            chosen_names = st.multiselect(
                "비교할 논문 (2편 이상 권장)",
                options=list(all_paper_dict.keys()),
                default=default_selected_titles,
                help="서재에 저장된 논문 중 비교분석을 수행할 논문들을 선택하세요."
            )

            chosen_papers = [all_paper_dict[name] for name in chosen_names]

            col_q, col_eng = st.columns([3.5, 1.8])
            with col_q:
                custom_q = st.text_input(
                    "중점 비교 항목 (선택)",
                    placeholder="예: 각 논문의 모델 아키텍처 차이점과 평가 지표를 집중 비교해 줘",
                    help="AI 에이전트가 특별히 주목해야 할 분석 관점이나 질문을 입력할 수 있습니다."
                )
            with col_eng:
                default_eng_idx = 0
                for i, eng in enumerate(PaperTranslator.SUPPORTED_ENGINES):
                    if "Gemini" in eng:
                        default_eng_idx = i
                        break
                comp_engine = st.selectbox(
                    "분석 모델",
                    options=PaperTranslator.SUPPORTED_ENGINES,
                    index=default_eng_idx,
                    format_func=engine_label,
                )

            st.divider()

            if st.button("비교분석 시작", type="primary", disabled=(len(chosen_papers) < 1), use_container_width=True):
                with loading("호두가 논문을 비교하고 있어요", f"선택한 {len(chosen_papers)}편의 구조와 평가 결과를 나란히 살펴봐요.", "think"):
                    res = MultiPaperComparativeAgent.analyze_papers(
                        papers=chosen_papers,
                        custom_question=custom_q,
                        engine=comp_engine,
                        api_key=sidebar_config.get("api_key"),
                        system_prompt=None
                    )


                if res.get("success"):
                    report_md = res.get("report_markdown")
                    st.session_state["latest_comparison_report"] = report_md
                    st.session_state["latest_comparison_engine"] = res.get("engine")
                    st.session_state["latest_comparison_papers"] = [p.get("title") for p in chosen_papers]

                    report_title = " & ".join([p.get("title")[:20] for p in chosen_papers[:3]])
                    archive_mgr.save_comparison_report(
                        title=f"{report_title} 비교분석",
                        paper_titles=[p.get("title") for p in chosen_papers],
                        report_markdown=report_md,
                        engine_name=res.get("engine")
                    )
                    show_state("비교한 내용을 정리했어요", "보고서를 서재에 저장했어요. 아래에서 읽거나 내려받을 수 있어요.", "done", "success")
                else:
                    show_state("보고서를 만들지 못했어요", str(res.get("error") or "잠시 후 다시 시도해 주세요."), "think", "error")

            if "latest_comparison_report" in st.session_state and st.session_state["latest_comparison_report"]:
                st.markdown("---")
                st.markdown(f"**분석 엔진**: `{st.session_state.get('latest_comparison_engine')}`")

                with st.container(border=True):
                    st.markdown(st.session_state["latest_comparison_report"], unsafe_allow_html=True)

                col_dl_md, col_dl_txt = st.columns([1, 1])
                with col_dl_md:
                    st.download_button(
                        "Markdown 다운로드",
                        data=st.session_state["latest_comparison_report"],
                        file_name="paper_comparison_report.md",
                        mime="text/markdown",
                        use_container_width=True
                    )

        with sub_tab_history:
            if not reports:
                show_state("비교한 내용도 모아둘게요", "서재의 논문을 골라 비교분석을 시작하면 보고서를 여기에서 다시 볼 수 있어요.", "read", "empty")
            else:
                for r_meta in reports:
                    r_id = r_meta.get("id")
                    with st.container(border=True):
                        col_r_info, col_r_btn, col_r_del = st.columns([3.6, 1.2, 0.9])
                        with col_r_info:
                            st.markdown(f"#### {r_meta.get('title')}")
                            st.caption(f"작성일시: {r_meta.get('created_at')} · 비교 대상: {r_meta.get('paper_count')}편 · 엔진: {r_meta.get('engine')}")
                            st.write(f"**대상 논문**: {', '.join(r_meta.get('papers', []))}")
                        with col_r_btn:
                            with st.popover("보고서 보기", use_container_width=True, key=f"view_rep_tab_{r_id}"):
                                full_rep = archive_mgr.get_comparison_report(r_id)
                                if full_rep:
                                    st.markdown(full_rep.get("markdown"), unsafe_allow_html=True)
                        with col_r_del:
                            with st.popover("삭제", icon=":material/delete:", use_container_width=True, key=f"del_rep_tab_pop_{r_id}"):
                                st.caption("이 보고서를 삭제합니다. 되돌릴 수 없습니다.")
                                if st.button("보고서 삭제", key=f"del_rep_tab_{r_id}", type="primary", use_container_width=True):
                                    archive_mgr.delete_comparison_report(r_id)
                                    st.rerun()


# ----------------------------------------------------------------------------------
# 📚 Helper: Apple Store Bookshelf Grid Renderer
# ----------------------------------------------------------------------------------
def _render_bookshelf_grid(papers: List[Dict[str, Any]], archive_mgr: ArchiveManager, available_topics: List[str], prefix: str = "shelf", sidebar_config: Optional[Dict[str, Any]] = None):
    """Renders a grid of realistic floating digital book covers with live renaming, migration & shelf racks."""
    if not papers:
        show_state("표시할 논문이 없어요", "다른 컬렉션을 열거나 검색 조건을 바꿔 보세요.", "rest", "empty")
        return

    cols_per_row = 4
    for r_idx in range(0, len(papers), cols_per_row):
        row_papers = papers[r_idx:r_idx + cols_per_row]
        cols = st.columns(cols_per_row)

        for c_idx, p in enumerate(row_papers):
            with cols[c_idx]:
                folder_path = p.get("folder_path")
                full_title = p.get("title") or "Untitled"
                short_title = html_mod.escape(_get_display_title(full_title))
                full_title = html_mod.escape(full_title)
                cover_data_uri = p.get("cover_base64") or archive_mgr.get_paper_cover_base64(folder_path)
                is_selected = folder_path in st.session_state.get("selected_library_paper_paths", [])
                year_val = p.get("year", 2025)
                topic_val = p.get("topic", "General")

                # Pure White Book Tile Card
                with st.container(border=True):
                    # 1. Selection Checkbox + Topic Tag
                    col_sel, col_tag = st.columns([0.4, 2])
                    with col_sel:
                        chk = st.checkbox("선택", value=is_selected, key=f"chk_{prefix}_{r_idx}_{c_idx}", label_visibility="collapsed")
                        if chk != is_selected:
                            cur_sel = st.session_state.setdefault("selected_library_paper_paths", [])
                            if chk:
                                if folder_path not in cur_sel:
                                    cur_sel.append(folder_path)
                            else:
                                if folder_path in cur_sel:
                                    cur_sel.remove(folder_path)
                            st.rerun()
                    with col_tag:
                        st.caption(f"`{topic_val}`")

                    # 2. Digital Book Cover Frame (Clickable)
                    if cover_data_uri:
                        cover_html = f"""
                        <div class="goodnotes-book-cover-frame">
                            <div class="goodnotes-book-spine"></div>
                            <img class="goodnotes-cover-img" src="{cover_data_uri}" alt="{short_title}" />
                        </div>
                        """
                    else:
                        cover_html = f"""
                        <div class="goodnotes-book-cover-frame">
                            <div class="goodnotes-book-spine"></div>
                            <div class="goodnotes-fallback-cover">
                                <div class="goodnotes-fallback-badge">PDF</div>
                                <div class="goodnotes-fallback-title">{short_title}</div>
                                <div style="font-size: 0.7rem; opacity: 0.7;">{year_val}</div>
                            </div>
                        </div>
                        """
                    st.markdown(cover_html, unsafe_allow_html=True)

                    # 3. Essential Title & Meta
                    st.markdown(f"<div class='goodnotes-book-title-text' title='{full_title}'>{short_title}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='goodnotes-book-year-tag'>{year_val}년 발행</div>", unsafe_allow_html=True)

                    # 4. Action 1: Read in Split Reader
                    if st.button("열람하기 ›", key=f"read_{prefix}_{r_idx}_{c_idx}", type="primary", use_container_width=True):
                        resolved_key = None
                        if sidebar_config and isinstance(sidebar_config, dict):
                            resolved_key = sidebar_config.get("api_key")
                        if not resolved_key:
                            resolved_key, _ = KeyManager.get_active_key()
                        _open_paper_in_reader(folder_path, archive_mgr, p, api_key=resolved_key)
                        st.rerun()

                    # 5. Secondary actions grouped under one labelled popover (rename / move / delete)
                    with st.popover("더보기", icon=":material/more_horiz:", use_container_width=True, key=f"more_{prefix}_{r_idx}_{c_idx}"):
                        st.markdown("**제목 변경**")
                        new_t = st.text_input("새 논문 제목", value=full_title, key=f"ren_input_{prefix}_{r_idx}_{c_idx}", label_visibility="collapsed")
                        if st.button("제목 저장", key=f"ren_save_{prefix}_{r_idx}_{c_idx}", use_container_width=True):
                            if new_t.strip() and new_t.strip() != full_title:
                                archive_mgr.rename_paper(folder_path, new_t.strip())
                                st.rerun()

                        st.divider()
                        st.markdown("**컬렉션 이동**")
                        target_opts = ["(직접 입력)"] + [t for t in available_topics if t != topic_val]
                        chosen_opt = st.selectbox("이동할 컬렉션", target_opts, key=f"mv_sel_{prefix}_{r_idx}_{c_idx}")
                        if chosen_opt == "(직접 입력)":
                            target_dest = st.text_input("새 컬렉션 이름", placeholder="예: Speech AI", key=f"mv_custom_{prefix}_{r_idx}_{c_idx}")
                        else:
                            target_dest = chosen_opt
                        if st.button("이동하기", key=f"mv_btn_exec_{prefix}_{r_idx}_{c_idx}", use_container_width=True):
                            if target_dest.strip():
                                archive_mgr.move_paper_topic(folder_path, target_dest.strip())
                                st.rerun()

                        st.divider()
                        confirm_del = st.checkbox("이 논문을 삭제합니다", key=f"del_confirm_{prefix}_{r_idx}_{c_idx}")
                        if st.button("논문 삭제", icon=":material/delete:", key=f"del_{prefix}_{r_idx}_{c_idx}", disabled=not confirm_del, use_container_width=True):
                            archive_mgr.delete_paper(folder_path)
                            st.rerun()

        # Shelf Rack Separator
        st.markdown('<div class="goodnotes-shelf-rack"></div>', unsafe_allow_html=True)


def _get_display_title(title: str, max_chars: int = 40) -> str:
    """Returns a clean, readable essential title snippet."""
    clean = re.sub(r'\[.*?\]|\(.*?\)', '', title).strip()
    if len(clean) > max_chars:
        return clean[:max_chars].strip() + "..."
    return clean


def _open_paper_in_reader(folder_path: str, archive_mgr: ArchiveManager, meta_dict: Dict[str, Any], api_key: Optional[str] = None):
    """Helper to load archived paper into active session reader."""
    if not api_key:
        api_key, _ = KeyManager.get_active_key()

    pdf_path = os.path.join(folder_path, "paper.pdf")
    total_pages = PaperPDFParser.get_total_pages(pdf_path) if os.path.exists(pdf_path) else 1

    with loading("호두가 서재에서 논문을 꺼내고 있어요", "첫 페이지를 읽을 준비를 하고 있어요.", "read"):
        # Load 1st page translation
        page_1_data = PaperPDFParser.get_single_page_data(pdf_path, 1, folder_path)
        page_1_trans = PaperTranslator.translate_single_page(
            page_data=page_1_data,
            paper_title=meta_dict.get("title", ""),
            engine=st.session_state.get("selected_translation_engine", PaperTranslator.SUPPORTED_ENGINES[0]),
            custom_api_key=api_key,
            custom_prompt=st.session_state.get("custom_llm_prompt")
        )

    bundle = archive_mgr.load_paper_bundle(folder_path)
    bundle["total_pages"] = total_pages
    bundle["metadata"] = meta_dict

    st.session_state.current_paper_bundle = bundle
    st.session_state.current_page_num = 1
    st.session_state.page_translations = {1: page_1_trans}
    st.session_state._active_translation_engine = st.session_state.get("selected_translation_engine", PaperTranslator.SUPPORTED_ENGINES[0])
    st.session_state._active_custom_prompt = st.session_state.get("custom_llm_prompt")
