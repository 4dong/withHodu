"""
Moonlight Split Reader with Pixel-Perfect Soft Highlighter Alignment & Interactive Draggable AI Chatbot
"""

import os
import base64
import inspect
import streamlit as st
from typing import Dict, Any, Optional
from core.searcher import Paper
from core.math_formatter import AcademicMathFormatter
from core.visual_highlighter import VisualHighlighter

# ==============================================================================
# Pure JavaScript Controller Engine (Main DOM Native Execution)
# ==============================================================================
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
    Renders Moonlight split reading experience:
    - Left (6.2): Maximized Full-Height Native Vector SVG PDF Viewer (88vh)
    - Right (3.8): Full-Height Scrollable Korean Translation Pane (88vh) with Flawless KaTeX Math Rendering
    - Pixel-Perfect Soft Highlighter: Bound 1:1 to SVG Canvas dimensions with soft amber tint.
    - Native page navigation, single-pane viewing, and a keyboard-accessible question popover.
    """

    toolbar = st.container(key="reader_toolbar").columns([1, 1, 1.2, 1], vertical_alignment="center")
    with toolbar[0]:
        if st.button("← 목록", key="reader_back", help="서재 목록으로 돌아갑니다."):
            st.session_state.current_paper_bundle = None
            st.session_state.page_translations = {}
            st.session_state.current_page_num = 1
            st.rerun()
    with toolbar[1]:
        if st.button("이전", key="reader_prev", help="이전 페이지", disabled=current_page <= 1):
            st.session_state.current_page_num = current_page - 1
            st.rerun()
    with toolbar[2]:
        st.caption(f"{current_page} / {total_pages} 페이지")
    with toolbar[3]:
        if st.button("다음", key="reader_next", help="다음 페이지", disabled=current_page >= total_pages):
            st.session_state.current_page_num = current_page + 1
            st.rerun()

    # Edge arrows: a sticky zero-height bar whose ends reveal ‹ › on hover, so paging stays
    # reachable after scrolling or with the sidebar hidden. Plain buttons keep keyboard access.
    with st.container(key="reader_edge_nav"):
        if current_page > 1:
            with st.container(key="reader_edge_prev"):
                if st.button("이전 페이지", key="reader_edge_prev_btn", icon=":material/chevron_left:", help="이전 페이지"):
                    st.session_state.current_page_num = current_page - 1
                    st.rerun()
        if current_page < total_pages:
            with st.container(key="reader_edge_next"):
                if st.button("다음 페이지", key="reader_edge_next_btn", icon=":material/chevron_right:", help="다음 페이지"):
                    st.session_state.current_page_num = current_page + 1
                    st.rerun()

    view_mode = st.radio("읽기 방식", ["대역 보기", "원문", "번역"], horizontal=True, key="reader_view_mode")
    pairs = page_translation.get("pairs", [])
    svg_content = page_data.get("svg_content", "")
    img_path = page_data.get("image_path")

    # Native popover preserves keyboard, touch and rerun behavior without DOM-bound chat controls.
    from core.qa_agent import PaperChatAgent
    with st.popover("논문에 질문", use_container_width=False):
        st.markdown("#### 논문 질문")
        st.caption(f"{current_page}페이지의 내용과 논문 정보를 바탕으로 답변합니다.")
        history_key = f"paper_chat_{paper.id}"
        history = st.session_state.setdefault(history_key, [])
        with st.container(height=180, border=False):
            if not history:
                st.caption("핵심 내용이나 이해하기 어려운 수식을 질문해 보세요.")
            for message in history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
        with st.form(f"paper_chat_form_{paper.id}", clear_on_submit=True):
            question = st.text_input("질문", placeholder="이 페이지의 핵심은 무엇인가요?")
            send = st.form_submit_button("질문 보내기", type="primary")
        if send:
            if not question.strip():
                st.info("질문을 입력해 주세요.")
            elif not api_key:
                st.info("질문에 답변하려면 사이드바에서 API 키를 설정해 주세요.")
            else:
                with st.spinner("논문 내용을 확인하고 있습니다…"):
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


    if view_mode == "대역 보기":
        col_pdf, col_trans = st.columns([6.2, 3.8])
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
            font_sz = st.session_state.get("trans_font_size", 16)
            line_ht = st.session_state.get("trans_line_height", 1.85)
            trans_pane_html = VisualHighlighter.render_translation_paragraphs(
                pairs=pairs,
                current_page=current_page,
                font_size=font_sz,
                line_height=line_ht
            )
            st.markdown(trans_pane_html, unsafe_allow_html=True)

    # 5. Inject execution trigger directly into main DOM via modern st.html with DOM Lifecycle onload guarantee
    b64_js = base64.b64encode(CLIENT_CONTROLLER_JS.encode("utf-8")).decode("ascii")
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
    <script>{CLIENT_CONTROLLER_JS}</script>
    '''
    if hasattr(st, "html"):
        if "unsafe_allow_javascript" in inspect.signature(st.html).parameters:
            st.html(lifecycle_injector, unsafe_allow_javascript=True)
        else:
            st.html(lifecycle_injector)
    else:
        st.markdown(lifecycle_injector, unsafe_allow_html=True)
