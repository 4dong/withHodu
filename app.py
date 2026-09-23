"""
호두랑 (withHodu): paper reader, library, and essay archive
Google Scholar Search & Authentic Moonlight 3:1 Split Page Reader
"""

import os
import html
import base64
import time
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Dict, Any, Optional
import streamlit as st

# Set Streamlit Page Configuration
FAVICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "hodu", "favicon.png")
st.set_page_config(
    page_title="호두랑",
    page_icon=FAVICON if os.path.isfile(FAVICON) else "🐶",
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
import core.reading_store
import ui.library_view
import ui.components
import ui.sidebar
import ui.hodu
import ui.home
import ui.styles

importlib.reload(core.reading_store)
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
importlib.reload(ui.hodu)
importlib.reload(ui.home)
importlib.reload(ui.sidebar)
importlib.reload(ui.styles)

# Core imports
from core.searcher import AcademicSearcher, Paper
from core.downloader import ArchiveManager
from core.parser import PaperPDFParser
from core.translator import PaperTranslator
from core.recommender import IntentRecommender
from core.intent_copilot import IntentCopilotAgent
from core.key_manager import KeyManager
from core.reading_store import ReadingStore, LAYOUT_VERSION, engine_tier, prompt_key, tier_label

# UI imports
from ui.styles import CUSTOM_CSS
from ui.sidebar import render_sidebar
from ui.components import render_moonlight_split_page_reader
from ui.library_view import render_library_view
from ui.home import render_home
from ui.hodu import apply_theme, page_header, show_state, loading, state_html, walking

st.html(CUSTOM_CSS)
apply_theme()

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
HIGHLIGHTER_ENGINE_VERSION = LAYOUT_VERSION  # bump it in core/reading_store.py: drops session and stored pages
# A page with untranslated paragraphs stays cached this long, so reruns do not hit a rate-limited service again;
# opening it after that translates it again.
FAILED_PAGE_RETRY_SECONDS = 60


@st.cache_data(max_entries=64, show_spinner=False)
def _cached_page_data(pdf_path: str, page: int, paper_dir: str, pdf_mtime: float, layout_version: str) -> Dict[str, Any]:
    return PaperPDFParser.get_single_page_data(pdf_path, page, paper_dir)


def page_data_for(pdf_path: Optional[str], page: int, paper_dir: str) -> Dict[str, Any]:
    """Parsing a page takes ~0.4 s and every widget interaction reruns the script, so parse each page once."""
    if not pdf_path or not os.path.exists(pdf_path):
        return PaperPDFParser.get_single_page_data(pdf_path, page, paper_dir)
    return _cached_page_data(pdf_path, page, paper_dir, os.path.getmtime(pdf_path), LAYOUT_VERSION)


def stored_or_translate(store: ReadingStore, pdf_path: str, page: int, paper_title: str, engine: str,
                        api_key: Optional[str], custom_prompt: Optional[str], use_store: bool = True) -> Dict[str, Any]:
    """A stored translation at least as good as the engine's needs no API call; a new one is stored."""
    if use_store:
        stored = store.load_page(page, engine, custom_prompt)
        if stored:
            return stored
    result = PaperTranslator.translate_single_page(
        page_data=page_data_for(pdf_path, page, store.paper_dir), paper_title=paper_title,
        engine=engine, custom_api_key=api_key, custom_prompt=custom_prompt)
    store.save_page(page, result, custom_prompt)
    return result


@st.cache_resource
def _prefetch_state() -> Dict[str, Any]:
    """Outlives reruns, so the next page keeps translating while the reader turns pages."""
    return {"pool": ThreadPoolExecutor(max_workers=2, thread_name_prefix="hodu-prefetch"),
            "jobs": {}, "lock": threading.Lock()}


def _prefetch_key(store: ReadingStore, page: int, engine: str, custom_prompt: Optional[str]) -> tuple:
    return store.paper_dir, page, engine, prompt_key(custom_prompt)


def _translate_in_background(paper_dir: str, pdf_path: str, page: int, paper_title: str, engine: str,
                             api_key: Optional[str], custom_prompt: Optional[str]) -> Dict[str, Any]:
    # No st.* in here: the thread has no script run context. The page lands in the store.
    store = ReadingStore(paper_dir)
    result = PaperTranslator.translate_single_page(
        page_data=PaperPDFParser.get_single_page_data(pdf_path, page, paper_dir), paper_title=paper_title,
        engine=engine, custom_api_key=api_key, custom_prompt=custom_prompt)
    store.save_page(page, result, custom_prompt)
    return result


def prefetch_page(store: ReadingStore, pdf_path: str, page: int, paper_title: str, engine: str,
                  api_key: Optional[str], custom_prompt: Optional[str]) -> None:
    """Translates a page in the background unless it is stored or already under way."""
    state = _prefetch_state()
    key = _prefetch_key(store, page, engine, custom_prompt)
    with state["lock"]:
        now = time.time()
        for old_key, (future, started) in list(state["jobs"].items()):
            if future.done() and now - started > 600:
                del state["jobs"][old_key]
        if key in state["jobs"] or store.load_page(page, engine, custom_prompt):
            return
        state["jobs"][key] = (state["pool"].submit(_translate_in_background, store.paper_dir, pdf_path, page,
                                                   paper_title, engine, api_key, custom_prompt), now)


def next_page_status(store: ReadingStore, page: int, total_pages: int, engine: str,
                     custom_prompt: Optional[str]) -> str:
    """'pending' while the page translates in the background, 'ready' once it can open at once, else 'none'."""
    if page > total_pages:
        return "none"
    state = _prefetch_state()
    with state["lock"]:
        job = state["jobs"].get(_prefetch_key(store, page, engine, custom_prompt))
    if job and not job[0].done():
        return "pending"
    return "ready" if job or store.load_page(page, engine, custom_prompt) else "none"


def claim_prefetch(store: ReadingStore, page: int, engine: str, custom_prompt: Optional[str]) -> Optional[Future]:
    with _prefetch_state()["lock"]:
        job = _prefetch_state()["jobs"].pop(_prefetch_key(store, page, engine, custom_prompt), None)
    return job[0] if job else None


def wait_for_prefetch() -> None:
    """Blocks until background translations finish (used by tests)."""
    for future, _ in list(_prefetch_state()["jobs"].values()):
        try:
            future.result(timeout=180)
        except Exception:
            pass

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
    st.session_state["hodu_search_error"] = None
    try:
        with loading("논문을 찾고 있어요", search_query, "search"):
            searcher = AcademicSearcher()
            raw_papers = searcher.search(query=search_query, max_results=sidebar_config.get("max_results", 5))
            intent_data = None
            if raw_papers:
                intent_data = IntentRecommender.analyze_and_recommend(
                    query=search_query, retrieved_papers=raw_papers, api_key=sidebar_config.get("api_key"))
    except Exception:
        st.session_state["hodu_search_error"] = "잠시 후 다시 검색해 주세요. 이전 결과는 그대로 있어요."
        return
    st.session_state.current_topic = search_query
    st.session_state.search_results = raw_papers or []
    st.session_state.intent_recommendations = intent_data
    if raw_papers:
        st.session_state.current_paper_bundle = None
        st.session_state.page_translations = {}
        st.session_state.current_page_num = 1

from ui.library_view import render_library_view
from ui.essay.workspace import render_essay_workspace

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

    # 1. Search Trigger
    if sidebar_config.get("trigger_search") and sidebar_config.get("query"):
        trigger_search_flow(sidebar_config["query"], sidebar_config)

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


def resolve_api_key(api_key: Optional[str]) -> str:
    if api_key and len(str(api_key).strip()) >= 15:
        return api_key
    active_k, _ = KeyManager.get_active_key()
    return active_k or os.environ.get("GEMINI_API_KEY", "")


def open_saved_paper(paper_dir: str, archive_mgr: ArchiveManager, engine: str, api_key: Optional[str],
                     custom_prompt: Optional[str]) -> None:
    """Opens a saved paper at the page it was left on; that page comes from the store when it can."""
    pdf_path = os.path.join(paper_dir, "paper.pdf")
    bundle = archive_mgr.load_paper_bundle(paper_dir)
    meta = bundle.get("metadata") or {}
    meta.setdefault("topic", os.path.basename(os.path.dirname(paper_dir)))
    meta["folder_path"] = paper_dir
    bundle["metadata"] = meta
    bundle["total_pages"] = total_pages = PaperPDFParser.get_total_pages(pdf_path)
    title = meta.get("title", "")

    store = ReadingStore(paper_dir)
    start = min(max(int(store.progress().get("last_page") or 1), 1), total_pages)
    first = store.load_page(start, engine, custom_prompt)
    if not first:
        with loading(f"{start}페이지를 번역하고 있어요" if start > 1 else "첫 페이지를 번역하고 있어요", title, "read"):
            first = stored_or_translate(store, pdf_path, start, title, engine, resolve_api_key(api_key),
                                        custom_prompt, use_store=False)

    st.session_state.current_paper_bundle = bundle
    st.session_state.current_page_num = start
    st.session_state.page_translations = {start: first}
    st.session_state._active_translation_engine = engine
    st.session_state._active_custom_prompt = custom_prompt
    if start > 1:
        st.session_state._resume_notice = start


def process_paper_and_load(paper: Paper, topic: str, archive_mgr: ArchiveManager, api_key: Optional[str], engine: str = "⚡️ Google Neural (무료 · 무제한)", custom_prompt: Optional[str] = None):
    """Downloads the PDF, files it in the library and opens it where it was last left."""
    try:
        with loading("PDF를 내려받고 있어요", paper.title, "fetch"):
            pdf_path = archive_mgr.download_pdf(paper, topic)
        if not pdf_path or not os.path.exists(pdf_path):
            show_state("논문 원문을 가져오지 못했어요", "공개되지 않은 논문일 수 있어요. 원문 링크에서 출판사 페이지를 확인해 주세요.", "think", "error")
            return
        with loading("서재에 저장하고 있어요", paper.title, "organize"):
            paper_dir = archive_mgr.save_archive_bundle(topic=topic, paper=paper, pdf_path=pdf_path)
        open_saved_paper(paper_dir, archive_mgr, engine, api_key, custom_prompt)
    except Exception:
        show_state("논문을 여는 중 문제가 생겼어요", "검색 결과에서 다시 열어 주세요.", "think", "error")
        return
    st.rerun()


def render_active_paper_view(archive_mgr: ArchiveManager, sidebar_config: Dict[str, Any]):
    """Renders the clean Moonlight 3:1 split reader with background pre-fetching."""
    # Streamlit matches elements by position across reruns. The page-turn wait and the fallback
    # notice appear only on some pages, so they share one slot that exists on every run; otherwise
    # the previous page's panes stay on screen beside the new ones while the next page is prefetched.
    status_slot = st.empty()
    bundle = st.session_state.current_paper_bundle
    meta_dict = bundle.get("metadata", {})
    paper = Paper(**{k: v for k, v in meta_dict.items() if k in Paper.__annotations__})
    pdf_path = bundle.get("pdf_path")
    paper_dir = (os.path.dirname(os.path.abspath(pdf_path)) if pdf_path and os.path.isfile(pdf_path)
                 else archive_mgr.get_paper_dir(meta_dict.get("topic", "General"), paper))
    store = ReadingStore(paper_dir)

    total_pages = bundle.get("total_pages") or (PaperPDFParser.get_total_pages(pdf_path) if pdf_path else 1)
    current_page = st.session_state.get("current_page_num", 1)
    selected_engine = sidebar_config.get("selected_engine", "⚡️ Google Neural (무료 · 무제한)")
    api_key = resolve_api_key(sidebar_config.get("api_key"))
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
    # Formula pairs carry no text, and a page may hold only formulas or nothing translatable (references).
    cached_text_pairs = [p for p in cached_trans.get("pairs", []) if p.get("kind") != "equation"] if isinstance(cached_trans, dict) else []
    is_valid_cache = (
        isinstance(cached_trans, dict)
        and "pairs" in cached_trans
        and (cached_trans.get("target_engine") == selected_engine or cached_trans.get("from_store"))
        and (not cached_text_pairs or (
            any(p.get("bbox", {}).get("height") not in ["0%", "0.0%", "0.00%"] for p in cached_text_pairs)
            and not all(p.get("ko", "").strip() == p.get("en", "").strip() for p in cached_text_pairs)))
        and not (cached_trans.get("failed_count")
                 and time.time() - cached_trans.get("translated_at", 0) > FAILED_PAGE_RETRY_SECONDS)
    )

    if not is_valid_cache:
        # Wipe any stale or wrong-engine translation for this page before starting
        if current_page in st.session_state.page_translations:
            del st.session_state.page_translations[current_page]

        # "Retranslate" skips the store and any background job; its result still cannot replace a higher tier.
        page_trans = None if force_retrans else store.load_page(current_page, selected_engine, custom_prompt)
        job = claim_prefetch(store, current_page, selected_engine, custom_prompt)
        if page_trans is None and job and not force_retrans:
            # Turned to a page still translating in the background: wait for it instead of asking again.
            with walking(f"{current_page}페이지 번역 중", placeholder=status_slot):
                try:
                    page_trans = job.result(timeout=180)
                except Exception:
                    page_trans = None
        if page_trans is None:
            with walking(f"{current_page}페이지 번역 중", placeholder=status_slot):
                page_trans = stored_or_translate(store, pdf_path, current_page, paper.title, selected_engine,
                                                 api_key, custom_prompt, use_store=False)
        st.session_state.page_translations[current_page] = page_trans
        st.session_state._active_translation_engine = selected_engine
    else:
        page_trans = st.session_state.page_translations[current_page]
    page_data = page_data_for(pdf_path, current_page, paper_dir)
    store.record_page(current_page, total_pages)

    resume_page = st.session_state.pop("_resume_notice", None)
    if resume_page:
        st.toast(f"지난번엔 {resume_page}쪽까지 읽었어요! 거기서부터 펼쳐 둘게요.", icon="🔖")

    # The Gemini fallback and untranslated paragraphs share the one status slot.
    notices = []
    if page_trans.get("is_fallback"):
        notices.append(f"**Google 번역으로 전환됨**: {page_trans.get('fallback_reason', 'API 키 미등록')}. "
                       "수식까지 정확한 Gemini 번역을 쓰려면 사이드바의 **API 키 관리**에서 키를 확인해 주세요.")
    if page_trans.get("failed_count"):
        notices.append(f"**문단 {page_trans['failed_count']}개를 번역하지 못해 원문으로 표시했어요.** "
                       f"{page_trans.get('failure_reason') or ''} 1분 뒤 이 페이지를 다시 열면 다시 번역하고, "
                       "사이드바의 **현재 페이지 다시 번역**으로 바로 시도할 수도 있어요.")
    if notices:
        status_slot.warning("\n\n".join(notices), icon="⚠️")
    elif page_trans.get("from_store") and page_trans.get("stored_tier", 0) > engine_tier(selected_engine):
        status_slot.caption(f"🔖 전에 저장해 둔 {tier_label(page_trans['stored_tier'])} 번역이에요. 새로 번역하지 않았어요.")

    # The next page translates in the background into the store; turning the page never waits on it.
    # Started before the reader draws so the toolbar light shows it from the first frame.
    try:
        if st.session_state.get("auto_translate_mode", True) and (current_page + 1 <= total_pages):
            prefetch_page(store, pdf_path, current_page + 1, paper.title, selected_engine, api_key, custom_prompt)
    except Exception:
        pass  # The current page remains usable; the next page can retry when opened.

    # Render Moonlight 3:1 Split Screen with integrated action bar & Draggable AI Chatbot
    render_moonlight_split_page_reader(
        paper=paper,
        current_page=current_page,
        total_pages=total_pages,
        page_data=page_data,
        page_translation=page_trans,
        pdf_path=pdf_path,
        api_key=api_key,
        next_page_status=lambda: next_page_status(store, current_page + 1, total_pages, selected_engine, custom_prompt),
    )


if __name__ == "__main__":
    main()
