"""Hodu's welcome room. Reference art is displayed intact through CSS viewports."""

import html
from pathlib import Path

import streamlit as st


from ui.hodu import ASSET, reference_data as _reference_data, motion_toggle
from ui.hodu_emotions import emotion_html, emotion_script
SEARCH_MODE = "🔍 논문 검색"
LIBRARY_MODE = "📚 나의 서재 (Visual Library & AI 분석)"


def go_home():
    st.session_state["hodu_home"] = True
    st.session_state["hodu_navigation_epoch"] = st.session_state.get("hodu_navigation_epoch", 0) + 1


def enter_workspace(destination):
    """Run before sidebar widgets are instantiated; keep a reader available to resume."""
    st.session_state["hodu_home"] = False
    st.session_state["hodu_navigation_epoch"] = st.session_state.get("hodu_navigation_epoch", 0) + 1
    essay = destination == "essay"
    st.session_state["current_workspace"] = "essay" if essay else "paper"
    st.session_state["app_workspace_radio"] = "자기소개서" if essay else "학술 논문"
    st.session_state["paper_navigation"] = LIBRARY_MODE if destination == "library" else SEARCH_MODE
    if destination in ("search", "library"):
        if st.session_state.get("current_paper_bundle"):
            st.session_state["hodu_saved_reader"] = {
                key: st.session_state.get(key)
                for key in ("current_paper_bundle", "current_page_num", "page_translations", "page_data_cache")
            }
        st.session_state["current_paper_bundle"] = None
    elif destination == "reader" and not st.session_state.get("current_paper_bundle"):
        for key, value in st.session_state.get("hodu_saved_reader", {}).items():
            st.session_state[key] = value


def _pose(name):
    return f'<div class="hodu-art" aria-hidden="true"><div class="hodu-pose hodu-{name}"></div></div>'


def render_home():
    css = Path(__file__).with_name("home.css").read_text(encoding="utf-8")
    st.html(f"<style>{css}</style>")
    if ASSET.is_file():
        st.html(
            '<style>.hodu-pose { background-image: url("data:image/png;base64,'
            + _reference_data() + '"); }</style>',
        )
    else:
        st.warning("호두 그림을 불러오지 못했어요. 아래 버튼으로 작업을 시작할 수 있어요.")

    with st.container(key="hodu_home"):
        brand, settings = st.columns([3, 1], vertical_alignment="center")
        with brand:
            st.markdown('<div class="hodu-brand"><span class="hodu-brand-mark">h.</span>'
                        '<strong>호두랑</strong><span class="hodu-wordmark">withHodu</span></div>',
                        unsafe_allow_html=True)
        with settings:
            reduced = motion_toggle()
        if reduced:
            st.html('<style>.st-key-hodu_home *, .st-key-hodu_home *::before,'
                        '.st-key-hodu_home *::after {animation:none!important;transition:none!important}</style>')

        st.markdown(
            '<section class="hodu-welcome" aria-label="호두랑 시작 화면">'
            '<div class="hodu-welcome-copy"><h1>오늘도,<br>호두랑 한 장씩.</h1>'
            '<p class="hodu-intro">논문을 원문과 번역으로 나란히 읽고, 모아 두고, 자소서를 정리해요.</p></div>'
            '<div class="hodu-scene"><div class="hodu-floor" aria-hidden="true"></div>'
            '<div class="hodu-hero-dog">' + emotion_html() + '</div></div></section>',
            unsafe_allow_html=True,
        )

        st.html(emotion_script(reduced), unsafe_allow_javascript=True)

        choices = [
            ("search", "fetch", "논문 검색", "주제로 찾아 원문과 번역을 나란히 읽어요.", "논문 찾기"),
            ("library", "read", "나의 서재", "열어 본 논문을 다시 읽고 여러 편을 비교해요.", "서재 열기"),
            ("essay", "organize", "자소서", "사진 속 자소서를 글로 옮기고, 찾고, 다듬어요.", "자소서 열기"),
        ]
        for column, (destination, pose, title, description, label) in zip(st.columns(3, gap="medium"), choices):
            with column, st.container(key=f"hodu_choice_{destination}"):
                st.markdown(
                    f'<div class="hodu-choice-art">{_pose(pose)}</div><h3 class="hodu-choice-title">{title}</h3>'
                    f'<p class="hodu-choice-description">{description}</p>', unsafe_allow_html=True,
                )
                st.button(label, key=f"hodu_enter_{destination}",
                          type="primary" if destination == "search" else "secondary",
                          use_container_width=True, on_click=enter_workspace, args=(destination,))

        saved = st.session_state.get("hodu_saved_reader") or {}
        open_bundle = st.session_state.get("current_paper_bundle")
        bundle = open_bundle or saved.get("current_paper_bundle")
        if bundle:
            page = st.session_state.get("current_page_num") if open_bundle else saved.get("current_page_num")
            title = (bundle.get("metadata") or {}).get("title") or "제목 없는 논문"
            with st.container(key="hodu_resume"):
                text, action = st.columns([3, 1], vertical_alignment="center")
                with text:
                    st.markdown('<p class="hodu-resume-label">읽던 논문' + (f' · {int(page)}페이지' if page else '')
                                + '</p><p class="hodu-resume-title">' + html.escape(str(title)) + '</p>',
                                unsafe_allow_html=True)
                with action:
                    st.button("이어서 읽기 →", use_container_width=True,
                              on_click=enter_workspace, args=("reader",))
