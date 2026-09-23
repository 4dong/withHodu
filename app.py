"""
호두랑 (withHodu): English papers read side by side with a Korean translation, plus the library and essay lab.
This file only routes between screens; each screen lives in ui/.
"""

import os

import streamlit as st

FAVICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "hodu", "favicon.png")
st.set_page_config(
    page_title="호두랑",
    page_icon=FAVICON if os.path.isfile(FAVICON) else "🐶",
    layout="wide",
    initial_sidebar_state="auto"
)

from core.downloader import ArchiveManager  # noqa: E402 (set_page_config must run first)
from core.translator import PaperTranslator  # noqa: E402
from ui.essay.workspace import render_essay_workspace  # noqa: E402
from ui.hodu import apply_theme, show_state  # noqa: E402
from ui.home import render_home  # noqa: E402
from ui.library_view import render_library_view  # noqa: E402
from ui.reader import (HIGHLIGHTER_ENGINE_VERSION, open_saved_paper, render_active_paper_view,  # noqa: E402
                       wait_for_prefetch)  # noqa: F401 (tests wait on the prefetch thread through app)
from ui.search_view import render_search_page  # noqa: E402
from ui.sidebar import render_sidebar  # noqa: E402
from ui.styles import CUSTOM_CSS  # noqa: E402

st.html(CUSTOM_CSS)
apply_theme()

# A new parser/highlighter layout drops the pages translated under the old one.
if st.session_state.get("_highlighter_engine_version") != HIGHLIGHTER_ENGINE_VERSION:
    st.session_state._highlighter_engine_version = HIGHLIGHTER_ENGINE_VERSION
    st.session_state.page_translations = {}

st.session_state.setdefault("search_results", [])
st.session_state.setdefault("current_paper_bundle", None)
st.session_state.setdefault("current_topic", "")
st.session_state.setdefault("current_page_num", 1)
st.session_state.setdefault("page_translations", {})


def main():
    if st.session_state.get("hodu_home", True):
        render_home()
        return
    archive_mgr = ArchiveManager()
    bundle = st.session_state.get("current_paper_bundle")
    active_pdf = bundle.get("pdf_path") if bundle else None
    cur_p = st.session_state.get("current_page_num", 1)
    tot_p = bundle.get("total_pages", 1) if bundle else 1
    sidebar_config = render_sidebar(
        archive_mgr=archive_mgr,
        active_pdf_path=active_pdf,
        current_page=cur_p,
        total_pages=tot_p
    )

    # The library and the home "continue" card ask for a saved paper; open it where it was left.
    pending_dir = st.session_state.pop("_open_paper_dir", None)
    if pending_dir:
        try:
            open_saved_paper(pending_dir, archive_mgr, sidebar_config.get("selected_engine", PaperTranslator.SUPPORTED_ENGINES[0]),
                             sidebar_config.get("api_key"), sidebar_config.get("custom_prompt"))
        except Exception:
            show_state("논문을 여는 중 문제가 생겼어요", "나의 서재에서 다시 열어 주세요.", "think", "error")
            return
        st.rerun()

    # 🌐 Top-Level Workspace Routing (Essay vs Scholar Paper)
    # Essential: Dispatched before active paper bundle early return to protect reading session state!
    if sidebar_config.get("workspace") == "essay" or st.session_state.get("current_workspace") == "essay":
        render_essay_workspace()
        return

    # Mode 1: Active Split Reader View (Pure reading interface with zero top header clutter)
    if st.session_state.current_paper_bundle:
        try:
            render_active_paper_view(archive_mgr, sidebar_config)
        except Exception:
            show_state("페이지를 준비하지 못했어요", "연결 상태를 확인하고 다시 시도해 주세요.", "think", "error")
            retry, back = st.columns(2)
            with retry:
                if st.button("다시 시도", key="hodu_retry_reader", type="primary"):
                    st.rerun()
            with back:
                if st.button("목록으로", key="hodu_reader_error_back"):
                    st.session_state.current_paper_bundle = None
                    st.rerun()
        return

    # Mode 2: Visual Library & Multi-Paper AI Comparison Lab View
    if "나의 서재" in sidebar_config.get("mode", ""):
        render_library_view(archive_mgr, sidebar_config)
        return

    render_search_page(archive_mgr, sidebar_config)


if __name__ == "__main__":
    main()
