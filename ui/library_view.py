"""
Paper library: collections, every saved paper, and multi-paper comparison reports.
"""

import hashlib
import os
import html as html_mod
import shutil
import streamlit as st
from typing import Dict, Any, List, Optional
from core.downloader import ArchiveManager
from core.analyzer import MultiPaperComparativeAgent
from ui.sidebar import engine_label
from ui.hodu import page_header, show_state, loading
from core.translator import PaperTranslator
from core.parser import PaperPDFParser
from core.key_manager import KeyManager


def render_library_view(archive_mgr: ArchiveManager, sidebar_config: Dict[str, Any]):
    """Collections, all papers, and comparison reports."""

    if "goodnotes_active_folder" not in st.session_state:
        st.session_state["goodnotes_active_folder"] = None

    if "selected_library_paper_paths" not in st.session_state:
        st.session_state["selected_library_paper_paths"] = []

    all_papers = archive_mgr.get_all_archived_papers()
    topics = archive_mgr.list_archived_topics()
    reports = archive_mgr.list_comparison_reports()
    active_folder = st.session_state.get("goodnotes_active_folder")

    if active_folder == "_reports":
        page_header("비교분석 보고서")
    elif active_folder:
        page_header(f"{active_folder} 컬렉션")
    else:
        page_header("나의 서재")

    with st.container(key="library_toolbar", horizontal=True, vertical_alignment="center"):
        st.markdown(f'<p class="h-library-summary"><strong>{len(all_papers)}</strong>편의 논문'
                    f'<span>컬렉션 {len(topics)}개 · 보고서 {len(reports)}건</span></p>',
                    unsafe_allow_html=True, width="stretch")
        with st.popover("새 컬렉션", icon=":material/add:", width="content"):
            new_col_name = st.text_input("컬렉션 이름", placeholder="예: Diffusion Models")
            if st.button("만들기", key="btn_create_new_topic", type="primary", use_container_width=True) and new_col_name.strip():
                new_topic_dir = os.path.join(archive_mgr.base_dir, archive_mgr._sanitize_folder_name(new_col_name.strip()))
                os.makedirs(new_topic_dir, exist_ok=True)
                st.session_state["goodnotes_active_folder"] = new_col_name.strip()
                st.rerun()

    if active_folder:
        if st.button("← 서재 전체", key="btn_library_back"):
            st.session_state["goodnotes_active_folder"] = None
            st.rerun()

    tab_shelf, tab_all_root, tab_agent = st.tabs(["컬렉션", "전체 논문", "비교분석"])

    # ----------------------------------------------------------------------------------
    # Collections
    # ----------------------------------------------------------------------------------
    with tab_shelf:
        if not active_folder:
            if st.session_state.get("folder_delete_error"):
                st.error(st.session_state["folder_delete_error"])
                st.session_state["folder_delete_error"] = None
            if st.session_state.get("folder_delete_success"):
                st.success(st.session_state["folder_delete_success"])
                st.session_state["folder_delete_success"] = None

            col_collections, col_reports = st.columns([2.85, 1.15])

            with col_reports, st.container(key="library_reports_card"):
                st.markdown(f'<p class="h-report-title">비교분석 보고서</p>'
                            f'<p class="h-report-count">{len(reports)}건 저장됨</p>', unsafe_allow_html=True)
                if st.button("보고서 보기", key="btn_open_reports_vault", use_container_width=True):
                    st.session_state["goodnotes_active_folder"] = "_reports"
                    st.rerun()

            with col_collections:
                if not topics:
                    show_state("아직 컬렉션이 없어요", "논문 검색에서 논문을 열면 주제별 컬렉션에 보관돼요.", "organize", "empty")
                else:
                    cols_per_row = 2
                    for r_idx in range(0, len(topics), cols_per_row):
                        row_topics = topics[r_idx:r_idx + cols_per_row]
                        f_cols = st.columns(cols_per_row)

                        for c_idx, t in enumerate(row_topics):
                            with f_cols[c_idx]:
                                t_papers = archive_mgr.list_papers_in_topic(t)
                                safe_name = html_mod.escape(str(t))
                                with st.container(border=True, key=f"card_collection_{r_idx}_{c_idx}"):
                                    st.markdown(f'<p class="h-collection-name" title="{safe_name}">{safe_name}</p>'
                                                f'<p class="h-collection-count">논문 {len(t_papers)}편</p>',
                                                unsafe_allow_html=True)
                                    col_open, col_del = st.columns([3, 1], vertical_alignment="center")
                                    with col_open:
                                        if st.button("열기", key=f"btn_open_f_{t}_{r_idx}_{c_idx}", use_container_width=True):
                                            st.session_state["goodnotes_active_folder"] = t
                                            st.rerun()
                                    with col_del:
                                        if st.button("삭제", icon=":material/delete:", type="tertiary", key=f"del_topic_{t}_{r_idx}_{c_idx}", help="빈 컬렉션만 삭제할 수 있어요."):
                                            if len(t_papers) > 0:
                                                st.session_state["folder_delete_error"] = f"'{t}'에 논문 {len(t_papers)}편이 있어 삭제할 수 없어요. 논문을 옮기거나 삭제한 뒤 다시 시도해 주세요."
                                            else:
                                                topic_dir = os.path.join(archive_mgr.base_dir, t)
                                                if os.path.exists(topic_dir):
                                                    shutil.rmtree(topic_dir, ignore_errors=True)
                                                st.session_state["folder_delete_success"] = f"'{t}' 컬렉션을 삭제했어요."
                                            st.rerun()

            st.markdown('<p class="h-section-title">최근 논문</p>', unsafe_allow_html=True)
            _render_bookshelf_grid(all_papers[:8], archive_mgr, topics, prefix="rec_shelf", sidebar_config=sidebar_config)

        elif active_folder == "_reports":
            if not reports:
                show_state("저장된 보고서가 없어요", "비교분석 탭에서 논문을 골라 보고서를 만들 수 있어요.", "read", "empty")
            else:
                for idx, r_meta in enumerate(reports):
                    r_id = r_meta.get("id")
                    with st.container(border=True, key=f"card_report_vault_{idx}"):
                        col_r_info, col_r_actions = st.columns([4, 1.6])
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
            folder_papers = archive_mgr.list_papers_in_topic(active_folder)

            if folder_papers:
                with st.container(key="library_folder_actions", horizontal=True, horizontal_alignment="right"):
                    with st.popover("전체 이동", icon=":material/drive_file_move:"):
                        target_new_t = st.text_input("옮길 컬렉션 이름", placeholder="예: Speech AI", key=f"batch_mv_input_{active_folder}")
                        if st.button("이동하기", key=f"batch_mv_exec_{active_folder}", type="primary", use_container_width=True) and target_new_t.strip():
                            for fp in folder_papers:
                                archive_mgr.move_paper_topic(fp.get("folder_path"), target_new_t.strip())
                            st.session_state["goodnotes_active_folder"] = target_new_t.strip()
                            st.rerun()

                    with st.popover("컬렉션 삭제", icon=":material/delete:"):
                        st.warning(f"논문 {len(folder_papers)}편과 컬렉션이 함께 삭제됩니다. 되돌릴 수 없습니다.")
                        if st.button("컬렉션 삭제", key=f"del_entire_folder_{active_folder}", type="primary", use_container_width=True):
                            topic_dir = os.path.join(archive_mgr.base_dir, active_folder)
                            archive_mgr.delete_paper(topic_dir)
                            st.session_state["goodnotes_active_folder"] = None
                            st.rerun()

            if not folder_papers:
                show_state("이 컬렉션은 비어 있어요", "다른 컬렉션의 논문을 옮겨 오거나 논문 검색에서 추가하세요.", "rest", "empty")
            else:
                _render_bookshelf_grid(folder_papers, archive_mgr, topics, prefix=f"f_{active_folder}", sidebar_config=sidebar_config)

    # ----------------------------------------------------------------------------------
    # All papers
    # ----------------------------------------------------------------------------------
    with tab_all_root:
        if not all_papers:
            show_state("아직 서재가 비어 있어요", "논문 검색에서 논문을 열면 여기에 보관돼요.", "rest", "empty")
        else:
            col_s_q, col_s_t, col_s_sort = st.columns([2.5, 1.3, 1.2])
            with col_s_q:
                filter_q = st.text_input("제목·저자로 찾기", placeholder="제목이나 저자로 찾기", key="root_filter_q", label_visibility="collapsed")
            with col_s_t:
                topic_f = st.selectbox("컬렉션", ["전체"] + topics, key="root_topic_f", label_visibility="collapsed")
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

            sel_count = len(st.session_state["selected_library_paper_paths"])
            col_b_info, col_b_run, col_b_move, col_b_del = st.columns([2.5, 1.8, 1.5, 1.2], vertical_alignment="center")
            with col_b_info:
                st.markdown(f"선택 {sel_count}편")
            with col_b_run:
                if st.button("선택한 논문 비교분석", key="btn_batch_comp_root", disabled=(sel_count < 2), type="primary", use_container_width=True):
                    st.session_state["active_library_tab"] = "agent"
                    st.rerun()
            with col_b_move:
                with st.popover("선택 이동", icon=":material/drive_file_move:", disabled=(sel_count == 0), use_container_width=True):
                    dest_t = st.text_input("옮길 컬렉션", placeholder="예: Speech AI", key="dest_batch_t_input")
                    if st.button("이동하기", key="btn_batch_move_exec", type="primary", use_container_width=True) and dest_t.strip():
                        for p_path in st.session_state["selected_library_paper_paths"]:
                            archive_mgr.move_paper_topic(p_path, dest_t.strip())
                        st.session_state["selected_library_paper_paths"] = []
                        st.rerun()
            with col_b_del:
                with st.popover("선택 삭제", icon=":material/delete:", disabled=(sel_count == 0), use_container_width=True):
                    st.warning(f"선택한 논문 {sel_count}편을 삭제합니다. 되돌릴 수 없습니다.")
                    if st.button("삭제하기", key="btn_batch_del_root", type="primary", use_container_width=True):
                        for p_path in st.session_state["selected_library_paper_paths"]:
                            archive_mgr.delete_paper(p_path)
                        st.session_state["selected_library_paper_paths"] = []
                        st.rerun()

            _render_bookshelf_grid(filtered, archive_mgr, topics, prefix="root_all", sidebar_config=sidebar_config)

    # ----------------------------------------------------------------------------------
    # Comparison
    # ----------------------------------------------------------------------------------
    with tab_agent:
        st.caption("고른 논문의 구조, 평가 지표, 학습 방식을 비교한 보고서를 만들어요.")

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
            )

            chosen_papers = [all_paper_dict[name] for name in chosen_names]

            col_q, col_eng = st.columns([3.5, 1.8])
            with col_q:
                custom_q = st.text_input(
                    "중점 비교 항목 (선택)",
                    placeholder="예: 각 논문의 모델 아키텍처 차이점과 평가 지표를 집중 비교해 줘",
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

            if st.button("비교분석 시작", type="primary", disabled=(len(chosen_papers) < 1)):
                with loading("논문을 비교하고 있어요", f"{len(chosen_papers)}편", "think"):
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
                    show_state("보고서를 저장했어요", "", "done", "success")
                else:
                    show_state("보고서를 만들지 못했어요", str(res.get("error") or "잠시 후 다시 시도해 주세요."), "think", "error")

            if "latest_comparison_report" in st.session_state and st.session_state["latest_comparison_report"]:
                st.caption(f"분석 모델: {st.session_state.get('latest_comparison_engine')}")

                with st.container(border=True, key="card_report_latest"):
                    st.markdown(st.session_state["latest_comparison_report"], unsafe_allow_html=True)

                st.download_button(
                    "Markdown 다운로드",
                    data=st.session_state["latest_comparison_report"],
                    file_name="paper_comparison_report.md",
                    mime="text/markdown",
                )

        with sub_tab_history:
            if not reports:
                show_state("저장된 보고서가 없어요", "비교분석을 실행하면 여기에 저장돼요.", "read", "empty")
            else:
                for idx, r_meta in enumerate(reports):
                    r_id = r_meta.get("id")
                    with st.container(border=True, key=f"card_report_history_{idx}"):
                        col_r_info, col_r_btn, col_r_del = st.columns([3.6, 1.2, 0.9])
                        with col_r_info:
                            st.markdown(f"#### {r_meta.get('title')}")
                            st.caption(f"{r_meta.get('created_at')} · 논문 {r_meta.get('paper_count')}편 · {r_meta.get('engine')}")
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


def _plain_label(text: str) -> str:
    """Widget labels are Markdown; escape the characters that would format a paper title or start math."""
    return "".join("\\" + ch if ch in "\\`*_[]$~#<>|" else ch for ch in text)


def _render_bookshelf_grid(papers: List[Dict[str, Any]], archive_mgr: ArchiveManager, available_topics: List[str], prefix: str = "shelf", sidebar_config: Optional[Dict[str, Any]] = None):
    """Paper tiles in rows of four: the cover opens the reader; rename, move and delete sit under 더보기."""
    if not papers:
        show_state("표시할 논문이 없어요", "다른 컬렉션을 열거나 검색 조건을 바꿔 보세요.", "rest", "empty")
        return

    # A topic label only tells papers apart when the list mixes topics.
    show_topic = len({p.get("topic") for p in papers}) > 1
    cols_per_row = 4
    for r_idx in range(0, len(papers), cols_per_row):
        row_papers = papers[r_idx:r_idx + cols_per_row]
        cols = st.columns(cols_per_row)

        for c_idx, p in enumerate(row_papers):
            with cols[c_idx]:
                folder_path = p.get("folder_path")
                full_title = p.get("title") or "제목 없음"
                cover_data_uri = p.get("cover_base64") or archive_mgr.get_paper_cover_base64(folder_path)
                is_selected = folder_path in st.session_state.get("selected_library_paper_paths", [])
                year_val = p.get("year") or ""
                topic_val = p.get("topic", "General")
                # Keys become CSS classes, so the cover's key carries an ASCII digest of its place.
                tile_id = hashlib.md5(f"{prefix}_{r_idx}_{c_idx}".encode("utf-8")).hexdigest()[:10]

                with st.container(border=True, key=f"card_paper_{tile_id}"):
                    col_sel, col_tag = st.columns([0.4, 2], vertical_alignment="center")
                    with col_sel:
                        chk = st.checkbox("비교할 논문으로 선택", value=is_selected, key=f"chk_{prefix}_{r_idx}_{c_idx}", label_visibility="collapsed")
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
                        st.markdown(f'<p class="h-paper-topic">{html_mod.escape(str(topic_val))}</p>' if show_topic else "",
                                    unsafe_allow_html=True)

                    cover = f'url("{cover_data_uri}")' if cover_data_uri else "none"
                    st.html(f'<style>.st-key-paper_open_{tile_id} button{{--cover:{cover}}}</style>')
                    if st.button(_plain_label(full_title), key=f"paper_open_{tile_id}", help=_plain_label(full_title), use_container_width=True):
                        resolved_key = None
                        if sidebar_config and isinstance(sidebar_config, dict):
                            resolved_key = sidebar_config.get("api_key")
                        if not resolved_key:
                            resolved_key, _ = KeyManager.get_active_key()
                        _open_paper_in_reader(folder_path, archive_mgr, p, api_key=resolved_key)
                        st.rerun()
                    st.markdown(f'<p class="h-paper-year">{html_mod.escape(str(year_val))}</p>', unsafe_allow_html=True)

                    with st.popover("더보기", icon=":material/more_horiz:", use_container_width=True, key=f"more_{prefix}_{r_idx}_{c_idx}"):
                        new_t = st.text_input("제목", value=full_title, key=f"ren_input_{prefix}_{r_idx}_{c_idx}")
                        if st.button("제목 저장", key=f"ren_save_{prefix}_{r_idx}_{c_idx}", use_container_width=True):
                            if new_t.strip() and new_t.strip() != full_title:
                                archive_mgr.rename_paper(folder_path, new_t.strip())
                                st.rerun()

                        st.divider()
                        target_opts = ["(직접 입력)"] + [t for t in available_topics if t != topic_val]
                        chosen_opt = st.selectbox("컬렉션 이동", target_opts, key=f"mv_sel_{prefix}_{r_idx}_{c_idx}")
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


def _open_paper_in_reader(folder_path: str, archive_mgr: ArchiveManager, meta_dict: Dict[str, Any], api_key: Optional[str] = None):
    """Helper to load archived paper into active session reader."""
    if not api_key:
        api_key, _ = KeyManager.get_active_key()

    pdf_path = os.path.join(folder_path, "paper.pdf")
    total_pages = PaperPDFParser.get_total_pages(pdf_path) if os.path.exists(pdf_path) else 1

    with loading("첫 페이지를 번역하고 있어요", meta_dict.get("title", ""), "read"):
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
