"""Hodu's welcome room. Reference art is displayed intact through CSS viewports."""

from pathlib import Path

import streamlit as st


from ui.hodu import ASSET, reference_data as _reference_data, motion_toggle
from ui.hodu_animations import home_animation_html
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
            '<div class="hodu-welcome-copy"><p class="hodu-eyebrow">나의 작은 읽기 작업실</p>'
            '<h1>오늘도,<br>호두랑 한 장씩.</h1>'
            '<p class="hodu-intro">궁금한 논문을 찾고, 생각을 글로 정리해요.<br>'
            '호두가 곁에서 함께할게요.</p>'
            '<span class="hodu-greeting"><i></i> 호두가 기다리고 있어요</span></div>'
            '<div class="hodu-scene" aria-hidden="true">'
            '<div class="hodu-scene-note">같이 읽을까요?</div>'
            '<div class="hodu-floor"></div>'
            '<div class="hodu-hero-dog">' + home_animation_html() + '</div>'
            '<span class="hodu-scene-caption">한 장의 발견, 함께하는 즐거움.</span></div></section>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="hodu-section-heading"><h2>오늘은 무엇을 해볼까요?</h2>'
                    '<span>작은 시작도 좋아요.</span></div>', unsafe_allow_html=True)
        choices = [
            ("search", "01", "fetch", "논문검색", "궁금한 주제를 알려주세요.<br>원문과 번역을 나란히 읽어요.", "논문 찾으러 가기"),
            ("library", "02", "read", "나의서재", "모아 둔 논문을 다시 펼쳐요.<br>여러 논문을 함께 비교할 수도 있어요.", "서재 들어가기"),
            ("essay", "03", "organize", "자소서", "사진 속 글부터 나의 초안까지.<br>차근차근 모으고 다듬어요.", "글 정리하러 가기"),
        ]
        for column, (destination, number, pose, title, description, label) in zip(st.columns(3, gap="medium"), choices):
            with column, st.container(key=f"hodu_choice_{destination}"):
                st.markdown(
                    f'<div class="hodu-choice-art"><span class="hodu-number">{number}</span>'
                    f'{_pose(pose)}</div><h3 class="hodu-choice-title">{title}</h3>'
                    f'<p class="hodu-choice-description">{description}</p>', unsafe_allow_html=True,
                )
                st.button(label + "  →", key=f"hodu_enter_{destination}",
                          type="primary" if destination == "search" else "secondary",
                          use_container_width=True, on_click=enter_workspace, args=(destination,))

        saved = st.session_state.get("hodu_saved_reader") or {}
        bundle = st.session_state.get("current_paper_bundle") or saved.get("current_paper_bundle")
        if bundle:
            with st.container(key="hodu_resume"):
                text, action = st.columns([3, 1], vertical_alignment="center")
                with text:
                    st.markdown("**펼쳐 둔 논문이 있어요.**")
                    st.caption("읽던 페이지에서 호두와 계속 읽어보세요.")
                with action:
                    st.button("이어서 읽기 →", use_container_width=True,
                              on_click=enter_workspace, args=("reader",))

        st.markdown('<footer class="hodu-footer"><span>withHodu · 읽고, 모으고, 나답게 쓰기</span>'
                    '<span>서두르지 않아도 괜찮아요.</span></footer>', unsafe_allow_html=True)
