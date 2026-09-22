"""
Reader styles: the reader toolbar, the PDF and translation panes with their paired highlights, formulas,
report tables, and the page edge arrows. Colours, surfaces and shared controls come from ui/hodu.css.
"""

CUSTOM_CSS = """
<style>
    [data-testid="stAppDeployButton"], [data-testid="stToolbarActions"], footer, #MainMenu {
        display: none !important;
    }
    html, body, .stApp, div[data-testid="stAppViewContainer"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", "Segoe UI", Roboto, sans-serif !important;
        letter-spacing: -0.015em;
        background-color: var(--ap-bg) !important;
        color: var(--ap-text) !important;
    }

    /* Reader toolbar: always visible, one row — back, title, paging, view mode, question. */
    .stApp .st-key-reader_toolbar {
        gap: 8px !important; padding: 8px 10px; background: var(--ap-surface);
        border: 1px solid var(--ap-border); border-radius: 14px;
    }
    /* :not([kind^="header"]) lifts this above the shared button rule in hodu.css, which loads later. */
    .stApp .st-key-reader_toolbar button[kind]:not([kind^="header"]) {
        min-height: 38px; padding: 6px 12px !important; white-space: nowrap;
    }
    .stApp .st-key-reader_toolbar [data-testid="stElementContainer"]:has(.h-reader-title) { min-width: 0; flex: 1 1 0; }
    .h-reader-title {
        margin: 0; font-size: 14px; font-weight: 600; color: var(--ap-text);
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .h-reader-page {
        margin: 0; min-width: 64px; text-align: center; font-size: 13px; color: var(--ap-muted);
        white-space: nowrap; font-variant-numeric: tabular-nums;
    }
    .stApp .st-key-reader_toolbar [data-testid="stRadio"] { margin: 0 6px; }
    .stApp .st-key-reader_toolbar [data-testid="stRadio"] label { padding: 0; }

    /* Panes: one frame height that fits the window under the toolbar (page top 32 + toolbar 56 + gap 16 +
       bottom padding 24 + a little slack), so the page itself does not scroll. */
    .stApp [data-testid="stMain"]:has(.st-key-reader_toolbar) .block-container { padding-bottom: 24px !important; }
    .unified-reader-frame {
        height: calc(100dvh - var(--reader-offset, 130px)); min-height: 360px; box-sizing: border-box;
        overflow: hidden; background: var(--ap-surface); border: 1px solid var(--ap-border); border-radius: 14px;
    }
    .pdf-viewer-wrapper, .scrollable-trans-box {
        position: relative !important; height: 100%; overflow-y: auto; box-sizing: border-box; background: var(--ap-surface);
    }
    .st-key-reader_split [data-testid="stHorizontalBlock"] { position: relative; gap: 16px !important; }
    .reader-split-handle {
        position: absolute; top: 0; bottom: 0; left: var(--reader-split, 50%);
        transform: translateX(-50%); width: 16px; cursor: col-resize; touch-action: none; z-index: 80;
        display: flex; justify-content: center; align-items: center; border-radius: 6px;
    }
    .reader-split-handle::after { content: ""; width: 4px; height: 48px; border-radius: 4px; background: #b5c5bc; }
    .reader-split-handle:hover::after, .reader-split-handle:focus-visible::after { background: #397a5d; }
    .reader-split-handle:focus-visible { outline: 2px solid #397a5d; outline-offset: -2px; }
    .reader-resizing, .reader-resizing * { user-select: none !important; cursor: col-resize !important; }
    @media (min-width: 641px) {
        .st-key-reader_split [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {
            flex: 0 0 calc(var(--reader-split, 50%) - 8px) !important; width: calc(var(--reader-split, 50%) - 8px) !important; min-width: 0 !important;
        }
        .st-key-reader_split [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) {
            flex: 0 0 calc(100% - var(--reader-split, 50%) - 8px) !important; width: calc(100% - var(--reader-split, 50%) - 8px) !important; min-width: 0 !important;
        }
    }
    @media (max-width: 640px) { .reader-split-handle { display: none; } }
    .doc-para { overflow-wrap: anywhere; }
    .pdf-viewer-wrapper { width: 100% !important; }
    .scrollable-trans-box { padding: 20px 24px; }
    .pdf-viewer-wrapper::-webkit-scrollbar, .scrollable-trans-box::-webkit-scrollbar { width: 6px; }
    .pdf-viewer-wrapper::-webkit-scrollbar-thumb, .scrollable-trans-box::-webkit-scrollbar-thumb { background: #d5ddd8; border-radius: 6px; }
    .pdf-content-canvas { position: relative !important; width: 100% !important; display: block !important; line-height: 0 !important; font-size: 0 !important; }
    .pdf-svg-container { width: 100% !important; display: block !important; line-height: 0 !important; user-select: text !important; -webkit-user-select: text !important; }
    .pdf-svg-container svg { width: 100% !important; height: auto !important; display: block !important; }

    /* Paired highlight: the PDF box and its translation paragraph share one green, hover lighter, pinned deeper. */
    .pdf-highlight-overlay {
        position: absolute !important; box-sizing: border-box; margin: 0; padding: 0; z-index: 50; cursor: pointer;
        border: 2px solid transparent; border-radius: 4px; background: transparent; opacity: 0;
        transition: opacity 120ms ease, background-color 120ms ease, border-color 120ms ease;
    }
    .pdf-highlight-overlay:hover, .pdf-highlight-overlay.active {
        opacity: 1; z-index: 65; background: rgba(57, 122, 93, 0.12); border-color: #397a5d;
    }
    .pdf-highlight-overlay.pinned { opacity: 1; z-index: 75; background: rgba(49, 92, 73, 0.2); border-color: #315c49; }
    .pdf-hl-badge {
        position: absolute; top: -10px; left: 6px; padding: 1px 7px; border-radius: 999px; pointer-events: none;
        background: #315c49; color: #fff; font-size: 11px; font-weight: 700; line-height: 1.3; opacity: 0;
    }
    .pdf-highlight-overlay:hover .pdf-hl-badge,
    .pdf-highlight-overlay.active .pdf-hl-badge,
    .pdf-highlight-overlay.pinned .pdf-hl-badge { opacity: 1; }

    .doc-para {
        margin: 0 0 12px; padding: 10px 14px; border-radius: 10px; border-left: 3px solid transparent; cursor: pointer;
        color: var(--ap-text); transition: background-color 120ms ease, border-color 120ms ease;
    }
    .doc-para:hover, .doc-para.active { background: #eaf2ed; border-left-color: #397a5d; }
    .doc-para.pinned { background: #dcebe1; border-left-color: #315c49; }
    .doc-para-idx { margin-right: 6px; font-size: 12px; font-weight: 600; color: #8a978f; user-select: none; }
    /* Paragraph bodies are Markdown inside the pane: inherit the reader's size. */
    .doc-para p { margin: 0 0 .5em !important; font-size: inherit !important; line-height: inherit !important; color: inherit; }
    .doc-para p:last-child { margin-bottom: 0 !important; }
    /* Display formulas are the PDF's own rendering: natural size, scrolling when wider than the pane. */
    .doc-formula-frame { overflow-x: auto; background: var(--ap-surface); border: 1px solid var(--ap-border); border-radius: 10px; padding: 10px 12px; text-align: center; }
    .doc-formula-image { max-width: none !important; height: auto; display: inline-block; vertical-align: middle; }
    .doc-formula-missing { font-size: 13px; color: var(--ap-muted); }

    .katex {
        font-size: 1.04em !important; font-family: KaTeX_Main, "KaTeX_Math", "Times New Roman", Times, serif !important;
        user-select: text !important; -webkit-user-select: text !important; line-height: 1.25 !important;
    }
    .katex-display {
        margin: .5rem 0 !important; padding: .6rem .9rem !important; overflow-x: auto !important; overflow-y: hidden !important;
        max-width: 100% !important; text-align: center !important;
        background: #f4f7f5 !important; border: 1px solid var(--ap-border) !important; border-radius: 10px !important;
    }
    .katex-display > .katex { white-space: normal !important; text-align: center !important; }
    .katex .base { margin-top: 2px !important; margin-bottom: 2px !important; }
    .katex-error {
        color: #974f39 !important; background: #fff2ed !important; padding: 2px 4px !important; border-radius: 4px !important;
        font-size: .9em !important; font-family: ui-monospace, monospace !important;
    }

    /* Comparison report tables. */
    .stApp [data-testid="stMarkdownContainer"] table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: .92rem; background: var(--ap-surface); }
    .stApp [data-testid="stMarkdownContainer"] th { padding: .6rem .8rem; text-align: left; font-weight: 600; color: var(--ap-text); background: #f1f4f3; border-bottom: 1px solid var(--ap-border); }
    .stApp [data-testid="stMarkdownContainer"] td { padding: .6rem .8rem; vertical-align: top; line-height: 1.55; border-bottom: 1px solid var(--ap-border); }

    [data-testid="stPopoverBody"] {
        width: min(480px, calc(100vw - 24px)); max-width: calc(100vw - 24px); max-height: calc(100dvh - 32px);
        overflow-y: auto; background: var(--ap-surface); border-radius: 16px;
    }

    /* Edge arrows: sticky zero-height bar; each end is a hover zone at the main area's edge. */
    [data-testid="stLayoutWrapper"]:has(> .st-key-reader_edge_nav),
    .st-key-reader_edge_nav {
        position: sticky; top: 30vh; z-index: 90; height: 0; min-height: 0; overflow: visible; gap: 0;
        width: 100% !important; max-width: none !important; align-self: stretch !important;
    }
    [data-testid="stLayoutWrapper"]:has(> .st-key-reader_edge_nav) { margin-bottom: -1rem; }
    .st-key-reader_edge_prev, .st-key-reader_edge_next {
        position: absolute; top: 0; height: 40vh; width: calc(var(--ap-page-gutter) + 12px);
        display: flex; flex-direction: column; justify-content: center; padding-inline: 2px;
    }
    .st-key-reader_edge_prev { left: calc(-1 * var(--ap-page-gutter)); align-items: flex-start; }
    .st-key-reader_edge_next { right: calc(-1 * var(--ap-page-gutter)); align-items: flex-end; }
    .st-key-reader_edge_prev [data-testid="stElementContainer"],
    .st-key-reader_edge_next [data-testid="stElementContainer"] { width: auto !important; }
    .stApp .st-key-reader_edge_prev button, .stApp .st-key-reader_edge_next button {
        width: 28px; min-width: 28px; height: 72px; min-height: 72px; padding: 0 !important; border-radius: 999px !important;
        background: rgba(255, 255, 255, 0.92) !important; border: 1px solid var(--ap-border) !important;
        box-shadow: 0 4px 16px rgba(32, 43, 39, 0.12) !important; color: var(--ap-text) !important;
        opacity: 0; transition: opacity 150ms ease, background-color 150ms ease !important;
    }
    .st-key-reader_edge_prev button [data-testid="stMarkdownContainer"],
    .st-key-reader_edge_next button [data-testid="stMarkdownContainer"] {
        position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap;
    }
    .st-key-reader_edge_prev:hover button, .st-key-reader_edge_next:hover button,
    .st-key-reader_edge_prev button:focus-visible, .st-key-reader_edge_next button:focus-visible { opacity: 1; }
    .stApp .st-key-reader_edge_prev button:hover, .stApp .st-key-reader_edge_next button:hover {
        background: #edf3ef !important; color: var(--ap-primary) !important; border-color: var(--ap-primary) !important;
    }
    @media (hover: none) {
        .st-key-reader_edge_prev button, .st-key-reader_edge_next button { opacity: 0.75; }
    }
    .st-key-reader_edge_prev button:disabled, .st-key-reader_edge_next button:disabled { visibility: hidden !important; }

    @media (max-width: 768px) {
        .scrollable-trans-box { padding: 14px 16px; }
        .stApp .st-key-reader_toolbar { flex-wrap: wrap !important; }
        .stApp .st-key-reader_toolbar [data-testid="stElementContainer"]:has(.h-reader-title) { flex: 1 1 100%; order: -1; }
    }
    @media (max-width: 640px) {
        .st-key-reader_edge_nav, [data-testid="stLayoutWrapper"]:has(> .st-key-reader_edge_nav) { display: none; }
    }
    @media (prefers-reduced-motion: reduce) {
        .stApp *, .stApp *::before, .stApp *::after {
            animation: none !important; transition: none !important; scroll-behavior: auto !important;
        }
    }
</style>
"""
