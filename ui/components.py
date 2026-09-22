"""
Moonlight Split Reader with Pixel-Perfect Soft Highlighter Alignment & Interactive Draggable AI Chatbot
"""

import os
import base64
import inspect
import html
from pathlib import Path
import streamlit as st
from typing import Dict, Any, Optional
from core.searcher import Paper
from core.math_formatter import AcademicMathFormatter
from core.visual_highlighter import VisualHighlighter
from ui.hodu import loading

# ==============================================================================
# Pure JavaScript Controller Engine (Main DOM Native Execution)
# ==============================================================================
READER_LAYOUT_JS = Path(__file__).with_name("reader_layout.js").read_text(encoding="utf-8")

CLIENT_CONTROLLER_JS = """
(function() {
    var win = typeof window !== 'undefined' ? window : this;
    var doc = typeof document !== 'undefined' ? document : (win.document || {});

    // Helper: Precision relative scroll calculator (immune to scale, padding, and zoom)
    function scrollToTarget(elem, container) {
        if (!elem || !container) return;
        try {
            var elemRect = elem.getBoundingClientRect();
            var contRect = container.getBoundingClientRect();
            var relativeTop = elemRect.top - contRect.top;
            var targetScroll = container.scrollTop + relativeTop - (container.clientHeight / 3);
            container.scrollTo({ top: Math.max(0, targetScroll), behavior: 'smooth' });
        } catch(err) {
            try {
                elem.scrollIntoView({ behavior: 'smooth', block: 'center' });
            } catch(e) {}
        }
    }

    win._agCurrentPinnedId = win._agCurrentPinnedId || null;
    console.log("[Anti-Paper] 🚀 Native Highlighter Controller Active");

    // 1. Global Synchronized Highlighter Core Function
    var activatePair = function(id, active, source) {
        var numId = parseInt(id, 10);
        if (!numId) return;

        try {
            var hl = doc.getElementById('pdf-hl-' + numId);
            var para = doc.getElementById('para-item-' + numId);

            if (active) {
                if (hl) {
                    hl.classList.add('active');
                    hl.style.opacity = '1';
                }
                if (para) {
                    para.classList.add('active');
                }
                if (!win._agCurrentPinnedId) {
                    if (source === 'para' && hl) {
                        var pdfPane = hl.closest('.pdf-viewer-wrapper') || doc.querySelector('.pdf-viewer-wrapper');
                        if (pdfPane) scrollToTarget(hl, pdfPane);
                    } else if (source === 'hl' && para) {
                        var transPane = para.closest('.scrollable-trans-box') || doc.querySelector('.scrollable-trans-box');
                        if (transPane) scrollToTarget(para, transPane);
                    }
                }
            } else {
                if (hl && !hl.classList.contains('pinned')) {
                    hl.classList.remove('active');
                    hl.style.opacity = '';
                }
                if (para && !para.classList.contains('pinned')) {
                    para.classList.remove('active');
                }
            }
        } catch (err) {
            console.error("[Anti-Paper] activatePair error:", err);
        }
    };

    var togglePinPair = function(id, source) {
        var numId = parseInt(id, 10);
        if (!numId) return;

        try {
            var hl = doc.getElementById('pdf-hl-' + numId);
            var para = doc.getElementById('para-item-' + numId);
            var isCurrentlyPinned = (win._agCurrentPinnedId === numId) || 
                                    (para && para.classList.contains('pinned')) || 
                                    (hl && hl.classList.contains('pinned'));

            var allPinned = doc.querySelectorAll('.doc-para.pinned, .pdf-highlight-overlay.pinned');
            allPinned.forEach(function(el) { 
                el.classList.remove('pinned'); 
                if (el.classList.contains('pdf-highlight-overlay') && !el.classList.contains('active')) {
                    el.style.opacity = '';
                }
            });

            if (isCurrentlyPinned) {
                win._agCurrentPinnedId = null;
                if (para) para.classList.add('active');
                if (hl) {
                    hl.classList.add('active');
                    hl.style.opacity = '1';
                }
                console.log("[Anti-Paper] ⚪ Unpinned Pair:", numId);
            } else {
                win._agCurrentPinnedId = numId;
                var allActive = doc.querySelectorAll('.doc-para.active, .pdf-highlight-overlay.active');
                allActive.forEach(function(el) {
                    if (el.id !== ('para-item-' + numId) && el.id !== ('pdf-hl-' + numId)) {
                        el.classList.remove('active');
                        if (el.classList.contains('pdf-highlight-overlay')) el.style.opacity = '';
                    }
                });

                if (para) para.classList.add('pinned', 'active');
                if (hl) {
                    hl.classList.add('pinned', 'active');
                    hl.style.opacity = '1';
                }

                if (source === 'para' && hl) {
                    var pdfPane = hl.closest('.pdf-viewer-wrapper') || doc.querySelector('.pdf-viewer-wrapper');
                    if (pdfPane) scrollToTarget(hl, pdfPane);
                } else if (source === 'hl' && para) {
                    var transPane = para.closest('.scrollable-trans-box') || doc.querySelector('.scrollable-trans-box');
                    if (transPane) scrollToTarget(para, transPane);
                }
                console.log("[Anti-Paper] 📌 Pinned Pair:", numId, "source:", source);
            }
        } catch (err) {
            console.error("[Anti-Paper] togglePinPair error:", err);
        }
    };

    win._agActivatePair = activatePair;
    win._agTogglePinPair = togglePinPair;
    win._agPairHover = activatePair;
    win._agPairClick = togglePinPair;
    window._agActivatePair = activatePair;
    window._agTogglePinPair = togglePinPair;
    window._agPairHover = activatePair;
    window._agPairClick = togglePinPair;

    // Document-Level Event Delegation for 100% Robustness
    if (!win._agHighlighterDelegationInstalled) {
        win._agHighlighterDelegationInstalled = true;

        doc.addEventListener('mouseover', function(e) {
            var paraTarget = e.target.closest('.doc-para');
            if (paraTarget) {
                var pId = paraTarget.getAttribute('data-id');
                if (pId) activatePair(pId, true, 'para');
                return;
            }
            var hlTarget = e.target.closest('.pdf-highlight-overlay');
            if (hlTarget) {
                var hId = hlTarget.getAttribute('data-id');
                if (hId) activatePair(hId, true, 'hl');
                return;
            }
        }, true);

        doc.addEventListener('mouseout', function(e) {
            var paraTarget = e.target.closest('.doc-para');
            if (paraTarget) {
                var pId = paraTarget.getAttribute('data-id');
                if (pId && (!e.relatedTarget || !e.relatedTarget.closest('#para-item-' + pId))) {
                    activatePair(pId, false, 'para');
                }
                return;
            }
            var hlTarget = e.target.closest('.pdf-highlight-overlay');
            if (hlTarget) {
                var hId = hlTarget.getAttribute('data-id');
                if (hId && (!e.relatedTarget || !e.relatedTarget.closest('#pdf-hl-' + hId))) {
                    activatePair(hId, false, 'hl');
                }
                return;
            }
        }, true);

        doc.addEventListener('click', function(e) {
            var paraTarget = e.target.closest('.doc-para');
            if (paraTarget) {
                var pId = paraTarget.getAttribute('data-id');
                if (pId) togglePinPair(pId, 'para');
                return;
            }
            var hlTarget = e.target.closest('.pdf-highlight-overlay');
            if (hlTarget) {
                var hId = hlTarget.getAttribute('data-id');
                if (hId) togglePinPair(hId, 'hl');
                return;
            }
            // Outside click -> deselect all pinned
            if (!paraTarget && !hlTarget) {
                if (win._agCurrentPinnedId !== null) {
                    win._agCurrentPinnedId = null;
                    var allPinned = doc.querySelectorAll('.doc-para.pinned, .pdf-highlight-overlay.pinned, .doc-para.active, .pdf-highlight-overlay.active');
                    allPinned.forEach(function(el) {
                        el.classList.remove('pinned', 'active');
                        if (el.classList.contains('pdf-highlight-overlay')) el.style.opacity = '';
                    });
                    console.log("[Anti-Paper] ❌ Deselected all pins");
                }
            }
        }, true);
    }


})();
"""

def render_moonlight_split_page_reader(
    paper: Paper,
    current_page: int,
    total_pages: int,
    page_data: Dict[str, Any],
    page_translation: Dict[str, Any],
    pdf_path: Optional[str],
    api_key: Optional[str] = None
):
    """
    Renders the split reader:
    - Toolbar, always visible: back to the list, title, previous · page · next, view mode, question.
    - Left: the page as vector SVG (or image) with one highlight box per paragraph.
    - Right: the Korean translation, one paragraph per box, formulas in KaTeX.
    Hovering or clicking either side highlights its pair on the other.
    """
    pairs = page_translation.get("pairs", [])
    svg_content = page_data.get("svg_content", "")
    img_path = page_data.get("image_path")

    with st.container(key="reader_toolbar", horizontal=True, vertical_alignment="center", gap="small"):
        if st.button("← 목록", key="reader_back", help="논문 목록으로 돌아갑니다."):
            st.session_state.current_paper_bundle = None
            st.session_state.page_translations = {}
            st.session_state.current_page_num = 1
            st.rerun()
        safe_title = html.escape(paper.title or "")
        st.markdown(f'<p class="h-reader-title" title="{safe_title}">{safe_title}</p>',
                    unsafe_allow_html=True, width="stretch")
        if st.button("이전", key="reader_prev", help="이전 페이지", disabled=current_page <= 1):
            st.session_state.current_page_num = current_page - 1
            st.rerun()
        st.markdown(f'<p class="h-reader-page">{current_page} / {total_pages}</p>',
                    unsafe_allow_html=True, width="content")
        if st.button("다음", key="reader_next", help="다음 페이지", disabled=current_page >= total_pages):
            st.session_state.current_page_num = current_page + 1
            st.rerun()
        view_mode = st.segmented_control("읽기 방식", ["대역", "원문", "번역"], default="대역", required=True,
                                         key="reader_view", label_visibility="collapsed", width="content")

        with st.popover("보기 설정", icon=":material/text_fields:", width="content"):
            def save_typography():
                st.session_state.trans_font_size = st.session_state.reader_font_size
                st.session_state.trans_line_height = st.session_state.reader_line_height

            st.session_state.reader_font_size = st.session_state.get("trans_font_size", 20)
            st.session_state.reader_line_height = st.session_state.get("trans_line_height", 1.85)
            st.slider("번역 글자 크기", min_value=12, max_value=28, step=1,
                      format="%d px", key="reader_font_size", on_change=save_typography)
            st.slider("줄 간격", min_value=1.4, max_value=2.4, step=0.05,
                      key="reader_line_height", on_change=save_typography)
            st.caption("대역 화면의 가운데 구분선을 드래그해 너비를 조절하세요. 두 번 클릭하면 반반으로 돌아갑니다.")

        # Native popover preserves keyboard, touch and rerun behavior without DOM-bound chat controls.
        from core.qa_agent import PaperChatAgent
        with st.popover("질문", icon=":material/forum:", width="content"):
            st.caption(f"{current_page}페이지 내용과 논문 정보를 바탕으로 답해요.")
            history_key = f"paper_chat_{paper.id}"
            history = st.session_state.setdefault(history_key, [])
            with st.container(height=220 if history else "content", border=False):
                for message in history:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])
            with st.form(f"paper_chat_form_{paper.id}", clear_on_submit=True):
                question = st.text_input("질문", placeholder="이 페이지의 핵심은 무엇인가요?")
                send = st.form_submit_button("보내기", type="primary")
            if send:
                if not question.strip():
                    st.info("질문을 입력해 주세요.")
                elif not api_key:
                    st.info("질문에 답하려면 사이드바의 API 키 관리에서 키를 등록해 주세요.")
                else:
                    with loading("답을 찾고 있어요", f"{current_page}페이지", "think"):
                        try:
                            result = PaperChatAgent.answer_query(
                                user_query=question, paper=paper, current_page=current_page,
                                page_texts=[pair.get("en") or pair.get("ko", "") for pair in pairs],
                                chat_history=history, api_key=api_key)
                        except Exception:
                            result = {"success": False}
                    if result.get("success") and not result.get("model_used", "").startswith("로컬"):
                        history.extend([{"role": "user", "content": question},
                                        {"role": "assistant", "content": result["answer"]}])
                        st.rerun()
                    else:
                        st.error("답변을 가져오지 못했습니다. 연결 상태를 확인하고 다시 시도해 주세요.")

    # Edge arrows: a sticky zero-height bar whose ends reveal ‹ › on hover, so paging stays
    # reachable after scrolling or with the sidebar hidden. Plain buttons keep keyboard access.
    # Both ends render on every page (disabled and hidden at the first/last page): Streamlit matches
    # elements by position across reruns, so a missing end would leave a stale arrow behind.
    with st.container(key="reader_edge_nav"):
        with st.container(key="reader_edge_prev"):
            if st.button("이전 페이지", key="reader_edge_prev_btn", icon=":material/chevron_left:", help="이전 페이지", disabled=current_page <= 1):
                st.session_state.current_page_num = current_page - 1
                st.rerun()
        with st.container(key="reader_edge_next"):
            if st.button("다음 페이지", key="reader_edge_next_btn", icon=":material/chevron_right:", help="다음 페이지", disabled=current_page >= total_pages):
                st.session_state.current_page_num = current_page + 1
                st.rerun()

    if view_mode == "대역":
        with st.container(key="reader_split"):
            col_pdf, col_trans = st.columns(2, gap="small")
    else:
        col_pdf = col_trans = st.container()

    # 1. Left Column: Native Vector SVG Viewer with Neon Overlays (via VisualHighlighter)
    if view_mode != "번역":
        with col_pdf:
            pdf_canvas_html = VisualHighlighter.render_overlay_canvas(
                pairs=pairs,
                current_page=current_page,
                svg_content=svg_content,
                image_path=img_path
            )
            st.markdown(pdf_canvas_html, unsafe_allow_html=True)

    # 2. Right Column: Maximized Scrollable Translation Pane with KaTeX Math (via VisualHighlighter)
    if view_mode != "원문":
        with col_trans:
            font_sz = st.session_state.get("trans_font_size", 20)
            line_ht = st.session_state.get("trans_line_height", 1.85)
            trans_pane_html = VisualHighlighter.render_translation_paragraphs(
                pairs=pairs,
                current_page=current_page,
                font_size=font_sz,
                line_height=line_ht
            )
            st.markdown(trans_pane_html, unsafe_allow_html=True)

    # 5. Inject execution trigger directly into main DOM via modern st.html with DOM Lifecycle onload guarantee
    controller_js = CLIENT_CONTROLLER_JS + READER_LAYOUT_JS
    b64_js = base64.b64encode(controller_js.encode("utf-8")).decode("ascii")
    lifecycle_injector = f'''
    <svg width="0" height="0" style="display:none;" onload="
        if(!window._agControllerInstalled){{
            window._agControllerInstalled = true;
            try {{
                var s = document.createElement('script');
                s.textContent = decodeURIComponent(escape(atob('{b64_js}')));
                document.head.appendChild(s);
            }} catch(e) {{
                console.error('[Anti-Paper] Controller mount error:', e);
            }}
        }}
    "></svg>
    <script>{controller_js}</script>
    '''
    if hasattr(st, "html"):
        if "unsafe_allow_javascript" in inspect.signature(st.html).parameters:
            st.html(lifecycle_injector, unsafe_allow_javascript=True)
        else:
            st.html(lifecycle_injector)
    else:
        st.markdown(lifecycle_injector, unsafe_allow_html=True)
