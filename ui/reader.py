"""Split reader: stored or fresh page translations, background prefetch of the next page, and opening papers."""

import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, Optional

import streamlit as st

from core.downloader import ArchiveManager
from core.key_manager import KeyManager
from core.parser import PaperPDFParser
from core.reading_store import LAYOUT_VERSION, ReadingStore, engine_tier, prompt_key, tier_label
from core.searcher import Paper
from core.translator import PaperTranslator
from ui.components import render_moonlight_split_page_reader
from ui.hodu import loading, show_state, walking

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
