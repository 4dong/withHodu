"""
Comprehensive Sidebar with Reader Remote Controller, Multi-Engine Selector, and Live LLM Prompt Customizer
"""

import os
import streamlit as st
from typing import Dict, Any, Optional
from core.downloader import ArchiveManager, DEFAULT_ARCHIVE_ROOT
from core.key_manager import KeyManager
from core.translator import PaperTranslator, DEFAULT_ACADEMIC_PROMPT
from ui.home import go_home, enter_workspace, SEARCH_MODE, LIBRARY_MODE
from ui.hodu import sidebar_brand, motion_toggle

def engine_label(engine: str) -> str:
    """Display name for an engine value without its leading emoji."""
    return engine.split(" ", 1)[1] if " " in engine and not engine[0].isascii() else engine


PROMPT_PRESETS = {
    "학술 연구원 (원문 병기, 격식체)": DEFAULT_ACADEMIC_PROMPT,
    "쉬운 한국어 (자연스러운 설명)": """너는 뛰어난 학술 해설가이자 번역가야. 논문 내용을 한국어로 누구나 쉽게 이해할 수 있도록 명확하고 부드럽게 번역해 줘.
1. 지나치게 난해한 직역을 지양하고, 논문의 핵심 논리를 직관적으로 이해할 수 있는 자연스러운 한국어 문장으로 번역할 것.
2. 중요 핵심 용어는 괄호 안에 원문을 병기할 것 (예: 강화학습(Reinforcement Learning)).
입력된 문단 순서와 개수를 1:1로 맞춰 JSON 객체('translations': [...])로만 응답해 줘.""",
    "엄밀한 직역 (수식·전문용어 보존)": r"""너는 엄격한 학술 번역가이자 AI 연구원이야. 논문의 모든 수식, 파라미터, 전문 약어를 철저히 보존하고 1:1로 엄밀하게 번역해 줘.
1. 모든 수식, 변수, 기호, 첨자, 그리스 문자(예: $\hat{A}^i, \hat{x}_1^i, v_\theta, \lambda_1, \sigma^2, \Delta t$)는 절대로 한글 음역하지 말고 표준 LaTeX `$수식$` 또는 `$$수식$$`으로 정확하게 감싸서 출력할 것.
2. 모든 전문 용어와 기술 명칭은 원문을 그대로 유지하거나 괄호 병기할 것.
입력된 문단 순서와 개수를 1:1로 맞춰 JSON 객체('translations': [...])로만 응답해 줘."""
}

def render_sidebar(
    archive_mgr: ArchiveManager,
    active_pdf_path: Optional[str] = None,
    current_page: int = 1,
    total_pages: int = 1
) -> Dict[str, Any]:
    """Renders comprehensive sidebar with Prompt Customization, Multi-Engine Selection, and Workspace Switcher."""
    
    with st.sidebar:
        sidebar_brand()

    current_ws = st.session_state.get("current_workspace", "paper")
    mode = st.session_state.get("paper_navigation", SEARCH_MODE)
    active = "essay" if current_ws == "essay" else ("library" if mode == LIBRARY_MODE else "search")
    with st.sidebar.container(key="main_navigation"):
        for destination, label, icon in (
            ("search", "논문 검색", ":material/search:"),
            ("library", "나의 서재", ":material/book_2:"),
            ("essay", "자소서", ":material/edit_document:"),
        ):
            st.button(
                label,
                icon=icon,
                key=f"sidebar_nav_{destination}",
                type="primary" if active == destination else "secondary",
                use_container_width=True,
                on_click=enter_workspace,
                args=(destination,),
            )

    if current_ws == "essay":
        # Essay sections sit under the 자소서 entry instead of as tabs across the page.
        from ui.essay.workspace import ESSAY_SECTIONS, current_essay_section, select_essay_section
        section = current_essay_section()
        with st.sidebar.container(key="essay_section_nav"):
            for name, label, icon in ESSAY_SECTIONS:
                st.button(label, icon=icon, key=f"essay_section_{name}",
                          type="primary" if name == section else "tertiary",
                          use_container_width=True, on_click=select_essay_section, args=(name,))

    st.sidebar.button("← 호두랑 시작 화면", key="sidebar_home", type="tertiary", on_click=go_home, use_container_width=True)
    st.sidebar.divider()

    if current_ws == "essay":
        return _render_essay_sidebar()

    if "selected_translation_engine" not in st.session_state:
        st.session_state["selected_translation_engine"] = PaperTranslator.SUPPORTED_ENGINES[0]

    if "custom_llm_prompt" not in st.session_state:
        st.session_state["custom_llm_prompt"] = DEFAULT_ACADEMIC_PROMPT

    # 1. Current paper settings (back / prev / next live in the reader toolbar)
    if "current_paper_bundle" in st.session_state and st.session_state["current_paper_bundle"]:
        with st.sidebar.container(key="sidebar_reader"):
            st.markdown("**현재 논문**")

            selected_page = st.selectbox(
                "페이지 이동",
                options=list(range(1, total_pages + 1)),
                index=current_page - 1,
                format_func=lambda x: f"{x} / {total_pages} 페이지",
            )
            if selected_page != current_page:
                st.session_state["current_page_num"] = selected_page
                st.rerun()

            cur_idx = 0
            if st.session_state["selected_translation_engine"] in PaperTranslator.SUPPORTED_ENGINES:
                cur_idx = PaperTranslator.SUPPORTED_ENGINES.index(st.session_state["selected_translation_engine"])

            chosen_engine = st.selectbox(
                "번역 모델",
                options=PaperTranslator.SUPPORTED_ENGINES,
                index=cur_idx,
                format_func=engine_label,
            )
            if chosen_engine != st.session_state["selected_translation_engine"]:
                st.session_state["selected_translation_engine"] = chosen_engine
                st.session_state["page_translations"] = {}  # Wipe all cached pages on engine switch
                st.session_state["_active_translation_engine"] = chosen_engine
                st.rerun()

            # Re-translate Current Page Button
            if st.button("현재 페이지 다시 번역", use_container_width=True, help="선택한 모델과 프롬프트로 이 페이지를 다시 번역합니다."):
                if "page_translations" in st.session_state and current_page in st.session_state["page_translations"]:
                    del st.session_state["page_translations"][current_page]
                st.session_state["_force_retranslate"] = True
                st.rerun()

            # PDF Download
            if active_pdf_path and os.path.exists(active_pdf_path):
                with open(active_pdf_path, "rb") as pf:
                    st.download_button(
                        "원문 PDF 다운로드",
                        data=pf.read(),
                        file_name="paper.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

        st.sidebar.divider()
    else:
        # Model Selector on initial search screen
        cur_idx = 0
        if st.session_state["selected_translation_engine"] in PaperTranslator.SUPPORTED_ENGINES:
            cur_idx = PaperTranslator.SUPPORTED_ENGINES.index(st.session_state["selected_translation_engine"])

        chosen_engine = st.sidebar.selectbox(
            "번역 모델",
            options=PaperTranslator.SUPPORTED_ENGINES,
            index=cur_idx,
            format_func=engine_label,
        )
        if chosen_engine != st.session_state["selected_translation_engine"]:
            st.session_state["selected_translation_engine"] = chosen_engine
            st.rerun()

    # 3. Universal LLM Prompt Customizer (Exposed for fine-tuning translation behavior)
    with st.sidebar.expander("번역 프롬프트", expanded=False):
        st.caption("Gemini 번역에 쓰는 지시문이에요. Google 번역에는 적용되지 않아요.")
        preset_choice = st.selectbox("프롬프트 프리셋 선택", list(PROMPT_PRESETS.keys()))
        
        # Textarea with current prompt
        cur_prompt = st.text_area(
            "시스템 프롬프트 (수정 가능)",
            value=PROMPT_PRESETS.get(preset_choice, st.session_state["custom_llm_prompt"]),
            height=190
        )
        if cur_prompt != st.session_state["custom_llm_prompt"]:
            st.session_state["custom_llm_prompt"] = cur_prompt

        if st.button("프롬프트 기본값 초기화", use_container_width=True):
            st.session_state["custom_llm_prompt"] = DEFAULT_ACADEMIC_PROMPT
            st.rerun()

    # 4. Key Slot Management
    all_slots = KeyManager.get_all_slots()
    if "selected_key_slot_id" not in st.session_state:
        st.session_state["selected_key_slot_id"] = None

    active_api_key, active_slot = KeyManager.get_active_key(st.session_state.get("selected_key_slot_id"))

    # Smart Default Engine: If valid API key exists and no manual change yet, prioritize Gemini 3.7 Flash
    if "selected_translation_engine" not in st.session_state:
        if active_api_key and len(active_api_key) > 15:
            st.session_state["selected_translation_engine"] = PaperTranslator.SUPPORTED_ENGINES[1]
        else:
            st.session_state["selected_translation_engine"] = PaperTranslator.SUPPORTED_ENGINES[0]

    active_engine = st.session_state["selected_translation_engine"]

    if "Gemini" in active_engine and not active_api_key:
        st.sidebar.caption("Gemini 번역에는 API 키가 필요해요. 아래 API 키 관리에서 등록하세요.")

    with st.sidebar.expander("API 키 관리", expanded=False):
        if all_slots:
            slot_options = {s["id"]: f"{s.get('name')} ({KeyManager.mask_key(s.get('key'))})" + (" · 기본" if s.get('is_default') else "") for s in all_slots}
            
            # Find default slot index
            default_slot_id = next((s["id"] for s in all_slots if s.get("is_default")), all_slots[0]["id"])
            current_chosen_id = st.session_state["selected_key_slot_id"] or default_slot_id
            if current_chosen_id not in slot_options:
                current_chosen_id = default_slot_id

            chosen_slot_id = st.selectbox(
                "저장된 키 슬롯 선택",
                options=list(slot_options.keys()),
                index=list(slot_options.keys()).index(current_chosen_id),
                format_func=lambda x: slot_options[x]
            )
            if chosen_slot_id != st.session_state["selected_key_slot_id"]:
                st.session_state["selected_key_slot_id"] = chosen_slot_id
                st.rerun()

            col_k_def, col_k_del = st.columns(2)
            with col_k_def:
                is_cur_def = any(s["id"] == chosen_slot_id and s.get("is_default") for s in all_slots)
                if st.button("기본 키로 지정", disabled=is_cur_def, use_container_width=True):
                    KeyManager.set_default(chosen_slot_id)
                    st.session_state["selected_key_slot_id"] = chosen_slot_id
                    st.session_state["selected_translation_engine"] = PaperTranslator.SUPPORTED_ENGINES[1]
                    st.success("기본 키로 설정했어요.")
                    st.rerun()
            with col_k_del:
                if st.button("선택 키 삭제", use_container_width=True):
                    KeyManager.delete_slot(chosen_slot_id)
                    st.session_state["selected_key_slot_id"] = None
                    st.warning("키가 삭제되었습니다.")
                    st.rerun()

        st.divider()
        st.markdown("**새 키 등록**")
        new_name = st.text_input("키 이름", placeholder="예: 개인 Gemini 키")
        new_key = st.text_input("API 키", type="password", placeholder="AIzaSy...")
        
        col_save_btn, _ = st.columns([1.2, 0.8])
        with col_save_btn:
            if st.button("등록하고 기본 키로 사용", type="primary", use_container_width=True):
                if new_key.strip():
                    new_id = KeyManager.save_slot(new_name or "Gemini 유료 키", new_key, set_as_default=True)
                    st.session_state["selected_key_slot_id"] = new_id
                    st.session_state["selected_translation_engine"] = PaperTranslator.SUPPORTED_ENGINES[1]
                    st.success("키를 등록하고 기본 키로 설정했어요.")
                    st.rerun()
                else:
                    st.error("API Key를 입력해 주세요.")

    st.sidebar.divider()

    config = {
        "mode": mode,
        "query": "",
        "max_results": 5,
        "archive_dir": DEFAULT_ARCHIVE_ROOT,
        "selected_engine": active_engine,
        "api_key": active_api_key,
        "active_slot": active_slot,
        "custom_prompt": st.session_state.get("custom_llm_prompt", DEFAULT_ACADEMIC_PROMPT),
        "selected_archived_paper": None,
        "trigger_search": False
    }

    if mode == "🔍 논문 검색":
        config["max_results"] = st.sidebar.number_input("검색 건수", min_value=1, max_value=10, value=5)

    _render_maintenance_settings()
    return config


def _render_essay_sidebar() -> Dict[str, Any]:
    """Renders clean dedicated sidebar for Essay Archive & RAG workspace."""
    active_api_key, active_slot = KeyManager.get_active_key()
    all_slots = KeyManager.get_all_slots()

    if not active_api_key:
        st.sidebar.caption("Gemini API 키가 없어 로컬 검색과 규칙 검사만 사용해요.")

    with st.sidebar.expander("API 키 관리", expanded=False):
        if all_slots:
            slot_options = {s["id"]: f"{s.get('name')} ({KeyManager.mask_key(s.get('key'))})" + (" · 기본" if s.get('is_default') else "") for s in all_slots}
            default_slot_id = next((s["id"] for s in all_slots if s.get("is_default")), all_slots[0]["id"])
            current_chosen_id = st.session_state.get("selected_key_slot_id") or default_slot_id
            if current_chosen_id not in slot_options:
                current_chosen_id = default_slot_id

            chosen_slot_id = st.selectbox(
                "저장된 키 슬롯",
                options=list(slot_options.keys()),
                index=list(slot_options.keys()).index(current_chosen_id),
                format_func=lambda x: slot_options[x],
                key="essay_slot_select"
            )
            if chosen_slot_id != st.session_state.get("selected_key_slot_id"):
                st.session_state["selected_key_slot_id"] = chosen_slot_id
                st.rerun()

            col_def, col_del = st.columns(2)
            with col_def:
                is_cur_def = any(s["id"] == chosen_slot_id and s.get("is_default") for s in all_slots)
                if st.button("기본 키 지정", disabled=is_cur_def, use_container_width=True, key="essay_btn_set_def"):
                    KeyManager.set_default(chosen_slot_id)
                    st.session_state["selected_key_slot_id"] = chosen_slot_id
                    st.success("기본 키로 설정했어요.")
                    st.rerun()
            with col_del:
                if st.button("키 삭제", use_container_width=True, key="essay_btn_del_key"):
                    KeyManager.delete_slot(chosen_slot_id)
                    st.session_state["selected_key_slot_id"] = None
                    st.warning("키가 삭제되었습니다.")
                    st.rerun()

        st.divider()
        new_name = st.text_input("키 이름", placeholder="예: 개인 Gemini 키", key="essay_new_key_name")
        new_key = st.text_input("API 키", type="password", placeholder="AIzaSy...", key="essay_new_key_val")
        if st.button("새 키 등록", type="primary", use_container_width=True, key="essay_btn_reg_key"):
            if new_key.strip():
                new_id = KeyManager.save_slot(new_name or "Gemini 키", new_key, set_as_default=True)
                st.session_state["selected_key_slot_id"] = new_id
                st.success("키를 등록했어요.")
                st.rerun()

    _render_maintenance_settings()
    return {
        "workspace": "essay",
        "mode": "essay",
        "api_key": active_api_key,
        "active_slot": active_slot
    }



def _render_notebook_export():
    from core.notebook_export import DEFAULT_NOTEBOOK_ROOT, build_notebook_folder, reveal_folder
    from ui.essay.workspace import get_or_create_essay_repo

    st.caption("서재의 논문 PDF는 `논문/`에, 자소서는 `자소서/제목.txt`로 모읍니다. 각 폴더의 파일을 모두 골라 Gemini 노트북에 한 번에 올리세요.")
    if st.button("업로드 폴더 새로 모으기", key="btn_build_notebook_folder", type="primary", use_container_width=True):
        res = build_notebook_folder(ArchiveManager(), get_or_create_essay_repo())
        st.success(f"논문 {res['papers']}편 · 자소서 {res['essays']}건을 모았습니다.")
        if res["skipped_papers"]:
            st.caption(f"PDF가 없는 논문 {res['skipped_papers']}편은 제외했습니다.")
        if res["removed"]:
            st.caption(f"서재에서 빠진 파일 {res['removed']}개를 정리했습니다.")
    if st.button("폴더 열기", key="btn_reveal_notebook_folder", use_container_width=True):
        if not os.path.isdir(DEFAULT_NOTEBOOK_ROOT) or not reveal_folder(DEFAULT_NOTEBOOK_ROOT):
            st.warning("먼저 업로드 폴더를 모아 주세요.")
    st.caption(f"위치: `{DEFAULT_NOTEBOOK_ROOT}`", help="환경변수 NOTEBOOK_ARCHIVE_ROOT로 바꿀 수 있습니다.")


def _render_maintenance_settings():
    with st.sidebar.expander("Gemini 노트북 업로드", expanded=False):
        _render_notebook_export()
    with st.sidebar.expander("화면 설정", expanded=False):
        motion_toggle()
    with st.sidebar.expander("고급 설정", expanded=False):
        if st.button("캐시 초기화 및 새로고침", use_container_width=True, help="저장된 번역과 페이지 분석 결과를 지우고 다시 불러옵니다."):
            st.session_state.page_translations = {}
            st.session_state.page_data_cache = {}
            st.session_state["_highlighter_engine_version"] = "FORCE_REFRESH_" + str(os.urandom(4).hex())
            st.session_state["_force_retranslate"] = True
            try:
                st.cache_data.clear()
                st.cache_resource.clear()
            except Exception:
                pass
            st.rerun()
