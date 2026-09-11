"""
Antigravity Scholar: Clean, Minimalist Core Skeleton
Google Scholar Search & Authentic Moonlight 3:1 Split Page Reader
"""

import os
import html
import base64
from typing import Dict, Any, Optional
import streamlit as st

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="Antigravity Scholar",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="auto"
)

import importlib

# Dynamic module reload to prevent stale in-memory module bytecode in long-running Streamlit processes
import core.math_formatter
import core.key_manager
import core.translator
import core.downloader
import core.parser
import core.analyzer
import core.searcher
import core.verifier
import core.qa_agent
import core.recommender
import core.intent_copilot
import core.visual_highlighter
import ui.library_view
import ui.components
import ui.sidebar
import ui.styles

importlib.reload(core.math_formatter)
importlib.reload(core.key_manager)
importlib.reload(core.translator)
importlib.reload(core.downloader)
importlib.reload(core.parser)
importlib.reload(core.analyzer)
importlib.reload(core.searcher)
importlib.reload(core.verifier)
importlib.reload(core.qa_agent)
importlib.reload(core.recommender)
importlib.reload(core.intent_copilot)
importlib.reload(core.visual_highlighter)
importlib.reload(ui.library_view)
importlib.reload(ui.components)
importlib.reload(ui.sidebar)
importlib.reload(ui.styles)

# Core imports
from core.searcher import AcademicSearcher, Paper
from core.downloader import ArchiveManager
from core.parser import PaperPDFParser
from core.translator import PaperTranslator
from core.recommender import IntentRecommender
from core.intent_copilot import IntentCopilotAgent

# UI imports
from ui.styles import CUSTOM_CSS
from ui.sidebar import render_sidebar
from ui.components import render_moonlight_split_page_reader
from ui.library_view import render_library_view

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Global Client Enforcer: Disables macOS Autocorrect/Autocomplete (Prevents 'qwen' -> 'Owen' replacement) & Fixes Cmd+C
CLIENT_GLOBAL_ENFORCER = """
<script>
(function() {
    function disableAutocorrectAndSpellcheck(targetDoc) {
        if (!targetDoc) return;
        var inputs = targetDoc.querySelectorAll('input, textarea');
        inputs.forEach(function(el) {
            el.setAttribute('autocomplete', 'off');
            el.setAttribute('autocorrect', 'off');
            el.setAttribute('autocapitalize', 'off');
            el.setAttribute('spellcheck', 'false');
            el.spellcheck = false;
        });
    }

    function interceptShortcut(e) {
        var isC = e.key === 'c' || e.key === 'C' || e.keyCode === 67 || e.code === 'KeyC';
        if (isC) {
            if (e.metaKey || e.ctrlKey) {
                e.stopImmediatePropagation();
                return;
            }
            var tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
            if (tag !== 'input' && tag !== 'textarea' && !e.target.isContentEditable) {
                e.stopImmediatePropagation();
                e.preventDefault();
            }
        }
    }

    function enforceSidebarState(targetDoc) {
        if (!targetDoc) return;
        try {
            var savedState = localStorage.getItem('antigravity_sidebar_state');
            var sidebar = targetDoc.querySelector('section[data-testid="stSidebar"]');
            var collapseBtn = targetDoc.querySelector('button[data-testid="stSidebarCollapseButton"]') || targetDoc.querySelector('[data-testid="stSidebarCollapseButton"] button');
            if (sidebar && collapseBtn) {
                var isAriaCollapsed = collapseBtn.getAttribute('aria-expanded') === 'false';
                var isWidthZero = sidebar.offsetWidth < 50;
                var isCollapsed = isAriaCollapsed || isWidthZero;
                if (savedState === 'collapsed' && !isCollapsed) {
                    collapseBtn.click();
                } else if (savedState === 'expanded' && isCollapsed) {
                    collapseBtn.click();
                }
            }
        } catch(e) {}
    }

    try {
        var targets = [];
        if (window.parent && window.parent.document) targets.push(window.parent.document);
        if (window.top && window.top.document && targets.indexOf(window.top.document) === -1) targets.push(window.top.document);
        if (targets.indexOf(document) === -1) targets.push(document);

        targets.forEach(function(t) {
            if (!t) return;
            
            // Immediate pass
            disableAutocorrectAndSpellcheck(t);
            enforceSidebarState(t);

            // Focusin listener to enforce on any focused input
            t.addEventListener('focusin', function(e) {
                if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {
                    e.target.setAttribute('autocomplete', 'off');
                    e.target.setAttribute('autocorrect', 'off');
                    e.target.setAttribute('autocapitalize', 'off');
                    e.target.setAttribute('spellcheck', 'false');
                    e.target.spellcheck = false;
                }
            }, true);

            // Shortcut prevention
            t.addEventListener('keydown', interceptShortcut, true);
            t.addEventListener('keyup', function(e) {
                if ((e.metaKey || e.ctrlKey) && (e.key === 'c' || e.key === 'C')) {
                    e.stopImmediatePropagation();
                }
            }, true);

            // MutationObserver to continuously disable autocorrect and observe sidebar buttons
            if (window.MutationObserver && !t._antigravity_autocorrect_observer) {
                t._antigravity_autocorrect_observer = true;
                var observer = new MutationObserver(function() {
                    disableAutocorrectAndSpellcheck(t);
                });
                observer.observe(t.body || t.documentElement, { childList: true, subtree: true });
            }
        });
    } catch(err) {}
})();
</script>
"""

# Execute client global enforcer directly in main DOM
if hasattr(st, "html"):
    st.html(CLIENT_GLOBAL_ENFORCER)
else:
    st.markdown(CLIENT_GLOBAL_ENFORCER, unsafe_allow_html=True)

# -------------------------------------------------------------
# 0. Session State Initialization & Auto-Cache Invalidation
# -------------------------------------------------------------
HIGHLIGHTER_ENGINE_VERSION = "2026_08_25_v8_self_contained_hover_sync_guaranteed"

if st.session_state.get("_highlighter_engine_version") != HIGHLIGHTER_ENGINE_VERSION:
    st.session_state._highlighter_engine_version = HIGHLIGHTER_ENGINE_VERSION
    st.session_state.page_translations = {}
    st.session_state.page_data_cache = {}

if "current_view" not in st.session_state:
    st.session_state.current_view = "library"
if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = "전체"
if "search_query" not in st.session_state:
    st.session_state.search_query = ""
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "is_searching" not in st.session_state:
    st.session_state.is_searching = False
if "current_paper_bundle" not in st.session_state:
    st.session_state.current_paper_bundle = None
if "current_topic" not in st.session_state:
    st.session_state.current_topic = ""
if "intent_recommendations" not in st.session_state:
    st.session_state.intent_recommendations = None
if "copilot_chat_history" not in st.session_state:
    st.session_state.copilot_chat_history = []
if "current_page_num" not in st.session_state:
    st.session_state.current_page_num = 1
if "page_translations" not in st.session_state:
    st.session_state.page_translations = {}
if "auto_translate_mode" not in st.session_state:
    st.session_state.auto_translate_mode = True

def trigger_search_flow(search_query: str, sidebar_config: Dict[str, Any]):
    """Executes clean Google Scholar & arXiv search and intent analysis with in-canvas visual progress."""
    search_placeholder = st.empty()
    with search_placeholder.container(border=True):
        st.markdown(f"#### '{search_query}' 검색 중")
        st.markdown('<div class="shimmer-loader-bar"></div>', unsafe_allow_html=True)
        st.caption("Google Scholar와 arXiv에서 논문을 찾고 있습니다…")

    st.session_state.current_topic = search_query
    searcher = AcademicSearcher()
    raw_papers = searcher.search(
        query=search_query,
        max_results=sidebar_config.get("max_results", 5)
    )
    
    if raw_papers:
        st.session_state.search_results = raw_papers
        st.session_state.current_paper_bundle = None
        st.session_state.page_translations = {}
        st.session_state.current_page_num = 1
        
        # Analyze intent recommendations
        intent_data = IntentRecommender.analyze_and_recommend(
            query=search_query,
            retrieved_papers=raw_papers,
            api_key=sidebar_config.get("api_key")
        )
        st.session_state.intent_recommendations = intent_data
    else:
        st.session_state.search_results = []
        st.session_state.intent_recommendations = None
        st.warning(f"'{search_query}'에 대한 검색 결과가 없습니다.")

    search_placeholder.empty()

from ui.library_view import render_library_view
from ui.essay.workspace import render_essay_workspace

def main():
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

    # 🌐 Top-Level Workspace Routing (Essay vs Scholar Paper)
    # Essential: Dispatched before active paper bundle early return to protect reading session state!
    if sidebar_config.get("workspace") == "essay" or st.session_state.get("current_workspace") == "essay":
        render_essay_workspace()
        return

    # 1. Search Trigger
    if sidebar_config.get("trigger_search") and sidebar_config.get("query"):
        trigger_search_flow(sidebar_config["query"], sidebar_config)

    # Mode 1: Active Split Reader View (Pure reading interface with zero top header clutter)
    if st.session_state.current_paper_bundle:
        render_active_paper_view(archive_mgr, sidebar_config)
        return

    # Mode 2: Visual Library & Multi-Paper AI Comparison Lab View
    if "나의 서재" in sidebar_config.get("mode", ""):
        render_library_view(archive_mgr, sidebar_config)
        return

    # Header (Only shown during search / initial state)
    st.title("논문 검색")
    st.caption("관심 있는 연구를 찾고, 원문과 번역을 함께 읽으세요.")

    with st.form("main_paper_search"):
        query = st.text_input("연구 주제 또는 키워드", placeholder="예: 음성 합성, 검색 증강 생성")
        submitted = st.form_submit_button("논문 찾기", type="primary")
    if submitted:
        if query.strip():
            trigger_search_flow(query.strip(), sidebar_config)
            st.rerun()
        else:
            st.info("찾고 싶은 연구 주제를 입력해 주세요.")
    if st.session_state.search_results:
        render_search_results_view(archive_mgr, sidebar_config)
    else:
        st.caption("보관한 논문은 사이드바의 ‘나의 서재’에서 이어 읽을 수 있어요.")


def render_search_results_view(archive_mgr: ArchiveManager, sidebar_config: Dict[str, Any]):
    """Displays clean search results with an ultra-minimalist Apple Spotlight AI Re-search bar."""
    topic = st.session_state.current_topic
    papers = st.session_state.search_results

    # 1. 🤖 Ultra-Minimalist Apple Spotlight AI Re-search Bar (Gemini 3.5 Flash)
    with st.container(border=True):
        col_c_title, col_c_model = st.columns([3.5, 1.5])
        with col_c_title:
            st.markdown(
                """
                <span class="apple-store-eyebrow" style="color: #2563EB; margin-bottom: 0.15rem;">연구 주제 구체화</span>
                <div style="font-size: 1.25rem; font-weight: 800; color: #1D1D1F; letter-spacing: -0.02em;">
                    어떤 연구를 더 찾고 싶으세요?
                </div>
                """,
                unsafe_allow_html=True
            )
        with col_c_model:
            st.markdown(
                """
                <div style="text-align: right; margin-top: 0.3rem;">
                    <span style="background: #EFF4FF; color: #2563EB; font-weight: 700; font-size: 0.82rem; padding: 0.35rem 0.85rem; border-radius: 9999px; display: inline-flex; align-items: center; gap: 0.3rem;">
                        Gemini 3.5 Flash
                    </span>
                </div>
                """,
                unsafe_allow_html=True
            )

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
                    with st.spinner("찾으려는 연구에 맞춰 검색어를 다듬는 중…"):
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
            st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)
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
        with st.container(border=True):
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


def process_paper_and_load(paper: Paper, topic: str, archive_mgr: ArchiveManager, api_key: Optional[str], engine: str = "⚡️ Google Neural (무료 · 무제한)", custom_prompt: Optional[str] = None):
    """Downloads PDF with clean animated banner and prepares Page 1."""
    
    # Secure API key fallback if not provided directly
    effective_api_key = api_key
    if not effective_api_key or len(str(effective_api_key).strip()) < 15:
        active_k, _ = KeyManager.get_active_key()
        effective_api_key = active_k or os.environ.get("GEMINI_API_KEY", "")

    prog_container = st.empty()
    with prog_container.container():
        st.markdown(
            f"""
            <div class="translation-loading-card">
                <div class="translation-loading-header">
                    <div class="translation-spin-icon-box">
                        <div class="translation-spin-icon-inner">
                            <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2.3" fill="none" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="12" cy="12" r="10"></circle>
                                <line x1="2" y1="12" x2="22" y2="12"></line>
                                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                            </svg>
                        </div>
                    </div>
                    <div class="translation-loading-text-col">
                        <div class="translation-loading-title">
                            <span>원문을 불러와 1페이지를 번역하는 중</span>
                            <span class="loading-dots"><span></span><span></span><span></span></span>
                            <span class="translation-loading-engine-badge">{engine.split(' ')[1]}</span>
                        </div>
                        <div class="translation-loading-desc">
                            <b>'{html.escape(paper.title[:38])}...'</b>의 문단과 수식을 원문과 짝지어 번역하고 있습니다.
                        </div>
                    </div>
                </div>
                <div class="shimmer-loader-bar"></div>
                <div class="translation-skeleton-wrap">
                    <div class="translation-skeleton-line" style="width: 92%;"></div>
                    <div class="translation-skeleton-line" style="width: 78%;"></div>
                    <div class="translation-skeleton-line" style="width: 85%;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # 1. Download PDF
        pdf_path = archive_mgr.download_pdf(paper, topic)
        if not pdf_path or not os.path.exists(pdf_path):
            prog_container.empty()
            st.error(f"**'{paper.title}'**의 PDF를 가져오지 못했습니다.\n\n유료 구독이 필요하거나 공개되지 않은 논문일 수 있습니다. **[원문 링크]** 버튼으로 출판사 페이지를 확인해 주세요.")
            return

        # 2. Auto-crop & 180 DPI high-res page snapshot
        paper_dir = archive_mgr.get_paper_dir(topic, paper)
        total_pages = PaperPDFParser.get_total_pages(pdf_path) if pdf_path else 1
        page_1_data = PaperPDFParser.get_single_page_data(pdf_path, 1, paper_dir)

        # 3. Batch Translate Page 1 (< 0.8s)
        page_1_trans = PaperTranslator.translate_single_page(
            page_data=page_1_data,
            paper_title=paper.title,
            engine=engine,
            custom_api_key=effective_api_key,
            custom_prompt=custom_prompt
        )

        # 4. Save bundle
        archive_mgr.save_archive_bundle(topic=topic, paper=paper, pdf_path=pdf_path)

        # Update Session
        bundle = archive_mgr.load_paper_bundle(paper_dir)
        bundle["total_pages"] = total_pages
        st.session_state.current_paper_bundle = bundle
        st.session_state.current_page_num = 1
        st.session_state.page_translations = {1: page_1_trans}

    prog_container.empty()
    st.rerun()


def render_active_paper_view(archive_mgr: ArchiveManager, sidebar_config: Dict[str, Any]):
    """Renders the clean Moonlight 3:1 split reader with background pre-fetching."""
    bundle = st.session_state.current_paper_bundle
    meta_dict = bundle.get("metadata", {})
    paper = Paper(**{k: v for k, v in meta_dict.items() if k in Paper.__annotations__})
    pdf_path = bundle.get("pdf_path")
    paper_dir = archive_mgr.get_paper_dir(meta_dict.get("topic", "General"), paper)

    total_pages = bundle.get("total_pages") or (PaperPDFParser.get_total_pages(pdf_path) if pdf_path else 1)
    current_page = st.session_state.get("current_page_num", 1)
    selected_engine = sidebar_config.get("selected_engine", "⚡️ Google Neural (무료 · 무제한)")
    api_key = sidebar_config.get("api_key")
    if not api_key or len(str(api_key).strip()) < 15:
        active_k, _ = KeyManager.get_active_key()
        api_key = active_k or os.environ.get("GEMINI_API_KEY", "")
    custom_prompt = sidebar_config.get("custom_prompt")

    # Invalidate session cache if translation engine or custom prompt was changed
    last_engine = st.session_state.get("_active_translation_engine")
    last_prompt = st.session_state.get("_active_custom_prompt")
    force_retrans = st.session_state.pop("_force_retranslate", False)
    if last_engine != selected_engine or last_prompt != custom_prompt or force_retrans:
        st.session_state._active_translation_engine = selected_engine
        st.session_state._active_custom_prompt = custom_prompt
        if force_retrans and current_page in st.session_state.get("page_translations", {}):
            del st.session_state.page_translations[current_page]
        elif last_engine != selected_engine or last_prompt != custom_prompt:
            st.session_state.page_translations = {}

    # 1. Fetch current page translation if not in cache or if cached under different engine or empty bbox / raw english
    cached_trans = st.session_state.get("page_translations", {}).get(current_page)
    is_valid_cache = (
        cached_trans is not None
        and isinstance(cached_trans, dict)
        and "pairs" in cached_trans
        and len(cached_trans["pairs"]) > 0
        and cached_trans.get("target_engine") == selected_engine
        and any(p.get("bbox", {}).get("height") not in ["0%", "0.0%", "0.00%"] for p in cached_trans["pairs"])
        and not all(p.get("ko", "").strip() == p.get("en", "").strip() for p in cached_trans["pairs"])
    )

    if not is_valid_cache:
        # Wipe any stale or wrong-engine translation for this page before starting
        if current_page in st.session_state.page_translations:
            del st.session_state.page_translations[current_page]

        page_prog_holder = st.empty()
        with page_prog_holder.container():
            engine_label = selected_engine.split(' ')[1] if len(selected_engine.split(' ')) > 1 else selected_engine
            st.markdown(
                f"""
                <div class="translation-loading-card">
                    <div class="translation-loading-header">
                        <div class="translation-spin-icon-box">
                            <div class="translation-spin-icon-inner">
                                <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2.3" fill="none" stroke-linecap="round" stroke-linejoin="round">
                                    <circle cx="12" cy="12" r="10"></circle>
                                    <line x1="2" y1="12" x2="22" y2="12"></line>
                                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                                </svg>
                            </div>
                        </div>
                        <div class="translation-loading-text-col">
                            <div class="translation-loading-title">
                                <span>{current_page}페이지 번역 중</span>
                                <span class="loading-dots"><span></span><span></span><span></span></span>
                                <span class="translation-loading-engine-badge">{engine_label}</span>
                            </div>
                            <div class="translation-loading-desc">
                                LaTeX 수식 보존 및 전문 학술 한국어 1:1 대역 처리를 진행하고 있습니다.
                            </div>
                        </div>
                    </div>
                    <div class="shimmer-loader-bar"></div>
                    <div class="translation-skeleton-wrap">
                        <div class="translation-skeleton-line" style="width: 90%;"></div>
                        <div class="translation-skeleton-line" style="width: 75%;"></div>
                        <div class="translation-skeleton-line" style="width: 82%;"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            page_data = PaperPDFParser.get_single_page_data(pdf_path, current_page, paper_dir)
            page_trans = PaperTranslator.translate_single_page(
                page_data=page_data,
                paper_title=paper.title,
                engine=selected_engine,
                custom_api_key=api_key,
                custom_prompt=custom_prompt
            )
            # Explicitly overwrite session translation with fresh output
            st.session_state.page_translations[current_page] = page_trans
            st.session_state._active_translation_engine = selected_engine
        page_prog_holder.empty()
    else:
        page_data = PaperPDFParser.get_single_page_data(pdf_path, current_page, paper_dir)
        page_trans = st.session_state.page_translations[current_page]

    # 2. Background pre-fetch next page if auto mode
    if st.session_state.get("auto_translate_mode", True) and (current_page + 1 <= total_pages):
        next_page = current_page + 1
        cached_next = st.session_state.page_translations.get(next_page)
        is_next_valid = (
            cached_next is not None
            and isinstance(cached_next, dict)
            and "pairs" in cached_next
            and len(cached_next["pairs"]) > 0
            and cached_next.get("target_engine") == selected_engine
        )
        if not is_next_valid:
            next_data = PaperPDFParser.get_single_page_data(pdf_path, next_page, paper_dir)
            next_trans = PaperTranslator.translate_single_page(
                page_data=next_data,
                paper_title=paper.title,
                engine=selected_engine,
                custom_api_key=api_key,
                custom_prompt=custom_prompt
            )
            st.session_state.page_translations[next_page] = next_trans

    # Transparent Fallback Notice
    if page_trans.get("is_fallback"):
        st.warning(
            f"**Google 번역으로 전환됨**: {page_trans.get('fallback_reason', 'API 키 미등록')}. "
            f"수식까지 정확한 Gemini 번역을 쓰려면 사이드바의 **API 키 관리**에서 키를 등록해 주세요.",
            icon="ℹ️"
        )

    # Render Moonlight 3:1 Split Screen with integrated action bar & Draggable AI Chatbot
    render_moonlight_split_page_reader(
        paper=paper,
        current_page=current_page,
        total_pages=total_pages,
        page_data=page_data,
        page_translation=page_trans,
        pdf_path=pdf_path,
        api_key=api_key
    )


if __name__ == "__main__":
    main()
