"""
Paper library: collections, every saved paper, and multi-paper comparison reports.
"""

import hashlib
import os
import html as html_mod
import streamlit as st
from typing import Dict, Any, List, Optional
from core.downloader import ArchiveManager, DEFAULT_TOPIC
from core.analyzer import MultiPaperComparativeAgent
from ui.sidebar import engine_label
from ui.hodu import page_header, show_state, loading
from core.translator import PaperTranslator
from core.reading_store import ReadingStore, tier_label


def render_library_view(archive_mgr: ArchiveManager, sidebar_config: Dict[str, Any]):
    """Collections, all papers, and comparison reports."""

    if st.session_state.pop("library_reset_selection", False):
        for key in list(st.session_state):
            if key.startswith("library_check_"):
                del st.session_state[key]
    if "library_pending_folder" in st.session_state:
        st.session_state["library_folder"] = st.session_state.pop("library_pending_folder")
    st.session_state.setdefault("selected_library_paper_paths", [])
    all_papers = archive_mgr.get_all_archived_papers()
    topics = archive_mgr.list_archived_topics()
    reports = archive_mgr.list_comparison_reports()
    valid_paths = {p["folder_path"] for p in all_papers}
    st.session_state["selected_library_paper_paths"] = [
        p for p in st.session_state["selected_library_paper_paths"] if p in valid_paths
    ]
    page_header("나의 서재", "새로 읽는 논문은 기본 폴더에 모여요. 원하는 폴더로 차근차근 정리해 보세요.")
    tab_shelf, tab_agent = st.tabs(["논문", "비교분석"])
    with tab_shelf:
        with st.container(key="library_toolbar", horizontal=True, vertical_alignment="center"):
            st.markdown(f'<p class="h-library-summary"><strong>{len(all_papers)}</strong>편<span>내가 읽고 모은 논문</span></p>', unsafe_allow_html=True, width="stretch")
            with st.popover("새 폴더", icon=":material/create_new_folder:"):
                name = st.text_input("폴더 이름", placeholder="예: 음성 합성")
                if st.button("폴더 만들기", type="primary", disabled=not name.strip()):
                    safe = archive_mgr._sanitize_folder_name(name)
                    if not safe or safe == "_reports":
                        st.error("다른 폴더 이름을 입력해 주세요.")
                    elif safe in topics:
                        st.error("이미 있는 폴더예요.")
                    else:
                        os.makedirs(os.path.join(archive_mgr.base_dir, safe), exist_ok=True)
                        st.session_state["library_folder"] = safe
                        st.rerun()
        with st.container(key="library_filters"):
            folder_col, search_col, sort_col = st.columns([1.3, 2.5, 1.2])
            with folder_col:
                options = ["전체"] + topics
                if st.session_state.get("library_folder") not in options:
                    st.session_state["library_folder"] = DEFAULT_TOPIC
                folder = st.selectbox("폴더", options, key="library_folder", format_func=lambda t: "기본 폴더" if t == DEFAULT_TOPIC else t)
            with search_col:
                query = st.text_input("논문 검색", placeholder="제목이나 저자로 검색", key="library_query").strip().casefold()
            with sort_col:
                order = st.selectbox("정렬", ["최근 저장순", "최신 발행순", "제목순"])
        papers = [p for p in all_papers if (folder == "전체" or p.get("topic") == folder)
                  and (not query or query in str(p.get("title", "")).casefold()
                       or query in " ".join(p.get("authors") or []).casefold())]
        papers.sort(key=lambda p: str(p.get("title") or "").casefold() if order == "제목순" else str(p.get("year") or "") if order == "최신 발행순" else p.get("updated_at", ""), reverse=order != "제목순")
        selected = st.session_state["selected_library_paper_paths"]
        with st.container(key="library_actions", horizontal=True, vertical_alignment="center"):
            st.caption(f"{len(papers)}편" + (f" · {len(selected)}편 선택" if selected else ""), width="stretch")
            if selected:
                with st.popover("폴더로 이동", icon=":material/drive_file_move:"):
                    dest = st.selectbox("이동할 폴더", topics, format_func=lambda t: "기본 폴더" if t == DEFAULT_TOPIC else t)
                    if st.button("선택한 논문 이동", type="primary"):
                        try:
                            for path in list(selected):
                                archive_mgr.move_paper_topic(path, dest)
                            st.session_state["selected_library_paper_paths"] = []
                            st.session_state["library_reset_selection"] = True
                            st.toast("논문을 옮겼어요.")
                            st.rerun()
                        except (OSError, ValueError) as exc:
                            st.error(str(exc))
                with st.popover("삭제", icon=":material/delete:"):
                    confirm = st.checkbox(f"선택한 논문 {len(selected)}편을 삭제합니다")
                    if st.button("선택한 논문 삭제", disabled=not confirm):
                        for path in list(selected):
                            archive_mgr.delete_paper(path)
                        st.session_state["selected_library_paper_paths"] = []
                        st.rerun()
            elif folder not in ("전체", DEFAULT_TOPIC):
                with st.popover("폴더 관리", icon=":material/more_horiz:"):
                    st.caption("빈 폴더만 삭제할 수 있어요.")
                    if st.button("빈 폴더 삭제", disabled=any(p.get("topic") == folder for p in all_papers)):
                        try:
                            os.rmdir(os.path.join(archive_mgr.base_dir, folder))
                            st.session_state["library_pending_folder"] = DEFAULT_TOPIC
                            st.rerun()
                        except OSError:
                            st.error("폴더에 파일이 남아 있어 삭제할 수 없어요.")
        if not papers:
            show_state("검색 결과가 없어요" if query else "아직 논문이 없어요", "다른 검색어로 찾아보세요." if query else "논문 검색에서 읽기를 시작하면 기본 폴더에 저장돼요.", "read", "empty")
        else:
            _render_bookshelf_grid(papers, archive_mgr, topics, sidebar_config=sidebar_config)

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
    """Accessible reading list with stable paper identities and contextual actions."""
    if not papers:
        show_state("표시할 논문이 없어요", "다른 컬렉션을 열거나 검색 조건을 바꿔 보세요.", "rest", "empty")
        return

    for p in papers:
        path = p["folder_path"]
        uid = hashlib.md5(path.encode()).hexdigest()[:12]
        title = p.get("title") or "제목 없음"
        with st.container(key=f"library_row_{uid}"):
            with st.container(horizontal=True, vertical_alignment="center", key=f"library_line_{uid}"):
                selected = st.checkbox("논문 선택: " + title, value=path in st.session_state["selected_library_paper_paths"], key=f"library_check_{uid}", label_visibility="collapsed", width=32)
                paths = st.session_state["selected_library_paper_paths"]
                if selected != (path in paths):
                    paths.append(path) if selected else paths.remove(path)
                    st.rerun()
                with st.container(key=f"library_info_{uid}", width="stretch"):
                    if st.button(_plain_label(title), key=f"library_open_{uid}", type="tertiary", use_container_width=True):
                        _open_paper_in_reader(path)
                        st.rerun()
                    authors = p.get("authors") or []
                    author = ", ".join(authors[:2]) + (" 외" if len(authors) > 2 else "")
                    topic = "기본 폴더" if p.get("topic") == DEFAULT_TOPIC else p.get("topic", "")
                    meta = " · ".join(str(v) for v in [author, p.get("year"), topic] if v)
                    badge = _reading_badge(path)
                    badge_html = f'<br><span class="library-paper-progress">{html_mod.escape(badge)}</span>' if badge else ""
                    st.markdown(f'<p class="library-paper-meta">{html_mod.escape(meta)}{badge_html}</p>', unsafe_allow_html=True)
                with st.popover("", icon=":material/more_horiz:", help="논문 이동·제목 수정·삭제", key=f"library_more_{uid}"):
                    dest = st.selectbox("이동할 폴더", available_topics, index=available_topics.index(p["topic"]), format_func=lambda t: "기본 폴더" if t == DEFAULT_TOPIC else t, key=f"dest_{uid}")
                    if st.button("이동", disabled=dest == p["topic"], key=f"move_{uid}", use_container_width=True):
                        try:
                            archive_mgr.move_paper_topic(path, dest)
                            st.toast("논문을 옮겼어요.")
                            st.rerun()
                        except (OSError, ValueError) as exc:
                            st.error(str(exc))
                    st.divider()
                    new_title = st.text_input("논문 제목", value=title, key=f"title_{uid}")
                    if st.button("제목 저장", key=f"rename_{uid}", disabled=not new_title.strip() or new_title.strip() == title):
                        archive_mgr.rename_paper(path, new_title.strip())
                        st.rerun()
                    st.divider()
                    confirm = st.checkbox("이 논문을 삭제합니다", key=f"confirm_{uid}")
                    if st.button("논문 삭제", key=f"delete_{uid}", disabled=not confirm):
                        archive_mgr.delete_paper(path)
                        st.rerun()


def _open_paper_in_reader(folder_path: str):
    """The app opens it on the next run, at the page where it was left."""
    st.session_state["_open_paper_dir"] = folder_path


def _reading_badge(folder_path: str) -> str:
    """'12/22쪽까지 읽음 · 번역 8쪽 (Gemini 3.7)' from the paper's reading record."""
    store = ReadingStore(folder_path)
    progress = store.progress()
    tiers = store.translated_pages()
    parts = []
    if progress.get("last_page"):
        parts.append(f"🔖 {progress['last_page']}/{progress.get('total_pages') or '?'}쪽까지 읽음")
    if tiers:
        parts.append(f"번역 {len(tiers)}쪽 ({tier_label(max(tiers.values()))})")
    return " · ".join(parts)
