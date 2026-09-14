"""
Apple Store Design System: Ultra-Minimalist Canvas (var(--ap-bg)), Pure White Cards (#FFFFFF),
High-Contrast Dark Featured Cards (#000000), Massive SF Pro Typography, and var(--ap-primary) Accent Badges.
"""

CUSTOM_CSS = """
<style>
    :root {
        --ap-bg: #F8F5ED;
        --ap-surface: #FFFFFF;
        --ap-text: #39392E;
        --ap-muted: #747366;
        --ap-primary: #3F5947;
        --ap-border: #E5DFD0;
        --ap-control-radius: 12px;
        --ap-card-radius: 20px;
        --ap-panel-radius: 24px;
        --ap-page-gutter: 2rem;
    }
    .stApp [data-testid="stWidgetLabel"], .stApp [data-testid="stHeadingWithActionElements"],
    .stApp [data-baseweb="radio"], .stApp [data-testid="stExpander"] summary { color: var(--ap-text); }
    .stApp h1 { font-size: 2rem; font-weight: 700; }
    .stApp h2 { font-size: 1.5rem; }
    .stApp h3 { font-size: 1.25rem; }
    .stApp h4 { font-size: 1.1rem; }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4 { overflow-wrap: anywhere; }
    [data-testid="stSidebar"] { background: var(--ap-surface); border-right: 1px solid var(--ap-border); }
    [data-testid="stCaptionContainer"] { color: var(--ap-muted); opacity: 1; }
    [data-testid="stForm"] { background: var(--ap-surface); border-radius: var(--ap-card-radius); padding: 24px; }
    .ap-page-header { margin-bottom: 1.5rem; }
    .ap-page-header h1 { margin: 0; padding-bottom: .4rem; }
    .ap-page-header p { color: var(--ap-muted); margin: 0; }
    .ap-document-title { font-size: 1.1rem; font-weight: 650; overflow-wrap: anywhere; }
    .ap-badge { display: inline-block; font-size: .8rem; border-radius: 999px; padding: 4px 10px; background: #F0F1E7; color: var(--ap-muted); }
    button:focus-visible, input:focus-visible, textarea:focus-visible, [tabindex="0"]:focus-visible {
        outline: 3px solid var(--ap-primary) !important; outline-offset: 3px;
    }

    /* Hide Streamlit Deploy button and standard header actions */
    [data-testid="stAppDeployButton"], [data-testid="stToolbarActions"], footer, #MainMenu {
        display: none !important;
    }

    /* ------------------------------------------------------------- */
    /* 🍎 1. Apple Store Global Canvas & Typography                  */
    /* ------------------------------------------------------------- */
    html, body, .stApp, div[data-testid="stAppViewContainer"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", "Segoe UI", Roboto, sans-serif !important;
        letter-spacing: -0.015em;
        background-color: var(--ap-bg) !important;
        color: var(--ap-text) !important;
    }

    /* Top & Side Breathable Negative Space (Expanded Fullscreen Widescreen Layout) */
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 2.2rem !important;
        padding-left: var(--ap-page-gutter) !important;
        padding-right: var(--ap-page-gutter) !important;
        max-width: 100% !important;
        margin: 0 auto !important;
        transition: padding 0.25s ease, max-width 0.25s ease !important;
    }

    /* Apple Store Massive Section Header */
    .apple-store-hero {
        margin-bottom: 2rem;
    }
    .apple-store-eyebrow {
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--ap-primary);
        margin-bottom: 0.4rem;
        display: block;
    }
    .apple-store-title {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.035em;
        color: var(--ap-text);
        line-height: 1.1;
        margin-bottom: 0.5rem;
    }
    .apple-store-subtitle {
        font-size: 1rem;
        font-weight: 400;
        color: var(--ap-muted);
        letter-spacing: -0.015em;
        line-height: 1.4;
    }

    /* ------------------------------------------------------------- */
    /* 🖤 2. Apple Store Dark Featured Card (#000000)                */
    /* ------------------------------------------------------------- */
    .apple-dark-featured-card {
        background-color: var(--ap-surface) !important;
        color: var(--ap-text) !important;
        border-radius: 24px !important;
        padding: 1.25rem !important;
        box-shadow: none !important;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 0;
        position: relative;
        overflow: hidden;
        border: 1px solid var(--ap-border) !important;
        box-sizing: border-box;
    }
    .apple-dark-featured-card .apple-store-eyebrow {
        color: var(--ap-primary) !important;
        font-size: 0.8rem;
    }
    .apple-dark-title {
        font-size: 1.25rem;
        font-weight: 800;
        color: var(--ap-text);
        letter-spacing: -0.025em;
        line-height: 1.2;
        margin: 0.4rem 0;
    }
    .apple-dark-desc {
        font-size: 0.92rem;
        color: var(--ap-muted);
        line-height: 1.5;
        margin-bottom: 1.4rem;
    }
    .apple-dark-pill-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        background: #EDF1E3;
        backdrop-filter: blur(16px);
        padding: 0.45rem 0.9rem;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 700;
        color: var(--ap-text);
        width: fit-content;
        margin-bottom: 0;
    }

    /* ------------------------------------------------------------- */
    /* 🤍 3. Apple Store Pure White Cards (#FFFFFF)                  */
    /* ------------------------------------------------------------- */
    .stApp [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important;
        border-radius: var(--ap-card-radius) !important;
        border: none !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04) !important;
        transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.28s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    .stApp [data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: none !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04) !important;
    }

    /* Apple Store Topic Card Content */
    .apple-product-card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.6rem;
    }
    .apple-product-topic-name {
        font-size: 1.25rem;
        font-weight: 800;
        color: var(--ap-text);
        letter-spacing: -0.02em;
    }
    .apple-product-price-tag {
        font-size: 0.88rem;
        font-weight: 600;
        color: var(--ap-muted);
        margin-bottom: 1.2rem;
    }

    /* ------------------------------------------------------------- */
    /* 🔘 4. Apple Store Interactive Pill Buttons & Links           */
    /* ------------------------------------------------------------- */
    /* Streamlit Primary Button -> Apple Store Royal Blue Pill */
    button[kind="primary"], .stButton > button[kind="primary"] {
        background-color: var(--ap-primary) !important;
        color: #FFFFFF !important;
        border-radius: var(--ap-control-radius) !important;
        border: none !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        padding: 0.55rem 1.4rem !important;
        transition: all 0.2s ease !important;
        letter-spacing: -0.01em !important;
    }
    button[kind="primary"]:hover, .stButton > button[kind="primary"]:hover {
        background-color: #314937 !important;
        transform: none !important;
        box-shadow: 0 4px 14px rgba(63, 89, 71, 0.15) !important;
    }

    /* Streamlit Secondary Button -> Apple Store White/Gray Pill */
    button[kind="secondary"], .stButton > button[kind="secondary"] {
        background-color: var(--ap-bg) !important;
        color: var(--ap-text) !important;
        border-radius: var(--ap-control-radius) !important;
        border: 1px solid rgba(0, 0, 0, 0.04) !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 0.5rem 1.2rem !important;
        transition: all 0.2s ease !important;
    }
    button[kind="secondary"]:hover, .stButton > button[kind="secondary"]:hover {
        background-color: #E8E4D8 !important;
        color: var(--ap-primary) !important;
    }

    /* Apple Store Pill Tabs */
    [data-testid="stTabs"] [role="tablist"] {
        background-color: #E8E4D8 !important;
        padding: 4px !important;
        border-radius: var(--ap-control-radius) !important;
        gap: 4px !important;
        border-bottom: none !important;
        width: fit-content !important;
        max-width: 100%;
        overflow-x: auto;
        margin-bottom: 1.8rem !important;
    }
    [data-testid="stTabs"] [role="tab"] {
        border-radius: var(--ap-control-radius) !important;
        padding: 0.45rem 1.1rem !important;
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        color: var(--ap-muted) !important;
        border: none !important;
        background-color: transparent !important;
    }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: var(--ap-text) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
    }
    .stTabs [data-baseweb="tab-highlight"] {
        display: none !important;
    }

    /* ------------------------------------------------------------- */
    /* 🌟 Apple Clean Form Inputs & Text Areas                      */
    /* ------------------------------------------------------------- */
    div[data-testid="stTextInput"] input {
        border-radius: 10px !important;
        border: 1.5px solid #DCD5C6 !important;
        background-color: #FFFFFF !important;
        padding: 0.65rem 1rem !important;
        font-size: 0.96rem !important;
        color: var(--ap-text) !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: var(--ap-primary) !important;
        box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.18) !important;
    }

    div[data-testid="stTextArea"] textarea {
        border-radius: 12px !important;
        border: 1.5px solid #DCD5C6 !important;
        background-color: #FFFFFF !important;
        padding: 0.9rem 1.1rem !important;
        font-size: 1.02rem !important;
        line-height: 1.65 !important;
        color: var(--ap-text) !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04) !important;
        transition: all 0.2s ease !important;
        resize: vertical !important;
    }
    div[data-testid="stTextArea"] textarea:focus {
        border-color: var(--ap-primary) !important;
        box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.18) !important;
    }
    .apple-prompt-box-highlight {
        background: linear-gradient(135deg, rgba(0, 113, 227, 0.05) 0%, rgba(224, 86, 0, 0.04) 100%);
        border: 1.5px solid rgba(0, 113, 227, 0.24);
        border-radius: 20px;
        padding: 1.1rem 1.3rem;
        margin-top: 0.9rem;
        margin-bottom: 0.5rem;
        box-shadow: 0 6px 22px rgba(0, 113, 227, 0.08);
    }
    .apple-prompt-header-tag {
        font-size: 0.88rem;
        font-weight: 800;
        letter-spacing: -0.01em;
        color: var(--ap-primary);
        display: flex;
        align-items: center;
        gap: 0.4rem;
        margin-bottom: 0.6rem;
    }

    /* ------------------------------------------------------------- */
    /* 📖 5. Floating Book Presentation & Bookshelf                 */
    /* ------------------------------------------------------------- */
    .apple-book-card {
        background: #FFFFFF;
        border-radius: 20px;
        padding: 1.2rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
        display: flex;
        flex-direction: column;
        align-items: center;
        transition: transform 0.24s ease, box-shadow 0.24s ease;
    }
    .apple-book-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 16px 36px rgba(0, 0, 0, 0.08);
    }
    .goodnotes-book-cover-frame {
        position: relative;
        width: 100%;
        max-width: 165px;
        aspect-ratio: 3 / 4.15;
        background: #FFFFFF;
        border-radius: 6px 12px 12px 6px;
        box-shadow: 
            -3px 0 0 #DCD5C6,
            -6px 0 0 #A1A1A6,
            0 12px 28px rgba(0, 0, 0, 0.12);
        overflow: hidden;
        border: 1px solid rgba(0, 0, 0, 0.06);
        cursor: pointer;
        transition: transform 0.24s ease, box-shadow 0.24s ease;
    }
    .goodnotes-book-spine {
        position: absolute;
        top: 0;
        bottom: 0;
        left: 0;
        width: 10px;
        background: linear-gradient(to right, rgba(0,0,0,0.16), rgba(0,0,0,0.02) 80%, transparent);
        z-index: 10;
    }
    .goodnotes-cover-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }
    .goodnotes-fallback-cover {
        width: 100%;
        height: 100%;
        background: var(--ap-text);
        color: #FFFFFF;
        padding: 1.2rem 1rem;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-sizing: border-box;
    }
    .goodnotes-fallback-title {
        font-size: 0.85rem;
        font-weight: 700;
        line-height: 1.35;
        color: #FFFFFF;
    }
    .goodnotes-book-title-text {
        font-size: 0.88rem;
        font-weight: 700;
        line-height: 1.35;
        color: var(--ap-text);
        word-break: keep-all;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        min-height: 2.3rem;
        margin-top: 0.7rem;
        text-align: center;
    }
    .goodnotes-book-year-tag {
        font-size: 0.78rem;
        color: var(--ap-muted);
        font-weight: 600;
        margin-top: 0.2rem;
        text-align: center;
    }
    .goodnotes-shelf-rack {
        width: 100%;
        height: 6px;
        background: #E8E4D8;
        border-radius: 3px;
        margin-top: 0.5rem;
        margin-bottom: 2.2rem;
    }

    /* ------------------------------------------------------------- */
    /* 📄 6. Moonlight Split Reader Viewports                        */
    /* ------------------------------------------------------------- */
    .unified-reader-frame {
        border: 1px solid #E8E4D8;
        border-radius: 20px;
        background: #FFFFFF;
        height: 88vh;
        overflow: hidden;
        box-sizing: border-box;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
    }
    .scrollable-trans-box {
        position: relative !important;
        height: 100%;
        overflow-y: auto;
        padding: 1.6rem 1.8rem;
        box-sizing: border-box;
    }
    .scrollable-trans-box::-webkit-scrollbar {
        width: 5px;
    }
    .scrollable-trans-box::-webkit-scrollbar-thumb {
        background: #DCD5C6;
        border-radius: 10px;
    }

    /* 🔵 Translation Paragraph (Apple Blue Highlight on Hover / Pin) */
    .doc-para {
        margin-bottom: 1.15rem;
        padding: 0.85rem 1.1rem;
        border-radius: 12px;
        border-left: 4px solid transparent;
        background-color: transparent;
        transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1);
        cursor: pointer;
        transform: none !important;
    }
    .doc-para:hover, .doc-para.active {
        background-color: #EEF1DF !important;
        border-left: 4px solid var(--ap-primary) !important;
        box-shadow: 0 4px 16px rgba(0, 113, 227, 0.12) !important;
        color: var(--ap-text) !important;
        transform: none !important;
    }
    .doc-para.pinned {
        background-color: #E3EBD4 !important;
        border-left: 5px solid #476249 !important;
        box-shadow: 0 4px 20px rgba(0, 113, 227, 0.25) !important;
        color: var(--ap-text) !important;
        transform: none !important;
    }
    .doc-para-idx {
        font-weight: 800;
        color: var(--ap-primary);
        font-size: 0.84rem;
        margin-right: 0.5rem;
        user-select: none;
    }

    /* 🟡 PDF Viewport & Moonlight Luminous Neon Glow Highlight Overlay */
    .pdf-viewer-wrapper {
        position: relative !important;
        width: 100% !important;
        height: 100% !important;
        overflow-y: auto !important;
        background: #FFFFFF !important;
        box-sizing: border-box !important;
        scroll-behavior: smooth !important;
    }
    .pdf-viewer-wrapper::-webkit-scrollbar {
        width: 5px;
    }
    .pdf-viewer-wrapper::-webkit-scrollbar-thumb {
        background: #DCD5C6;
        border-radius: 10px;
    }
    .pdf-content-canvas {
        position: relative !important;
        width: 100% !important;
        display: block !important;
        line-height: 0 !important;
        font-size: 0 !important;
    }
    .pdf-highlight-overlay {
        position: absolute !important;
        pointer-events: auto !important;
        border-radius: 6px !important;
        margin: 0 !important;
        padding: 0 !important;
        transition: opacity 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease !important;
        opacity: 0;
        background-color: rgba(254, 240, 138, 0.15) !important;
        border: 1.5px solid transparent !important;
        box-shadow: none !important;
        z-index: 50 !important;
        cursor: pointer !important;
        box-sizing: border-box !important;
    }
    .pdf-highlight-overlay:hover, .pdf-highlight-overlay.active {
        opacity: 1 !important;
        background-color: rgba(254, 240, 138, 0.42) !important;
        border: 2px solid #F59E0B !important;
        box-shadow: 
            0 0 0 2px rgba(245, 158, 11, 0.45),
            0 4px 20px rgba(245, 158, 11, 0.32),
            inset 0 0 14px rgba(254, 240, 138, 0.35) !important;
        z-index: 65 !important;
        animation: luminous-glow-pulse 2.2s infinite ease-in-out !important;
    }
    .pdf-highlight-overlay.pinned {
        opacity: 1 !important;
        background-color: rgba(254, 240, 138, 0.52) !important;
        border: 2.5px solid #D97706 !important;
        box-shadow: 
            0 0 0 3px rgba(217, 119, 6, 0.55),
            0 6px 26px rgba(217, 119, 6, 0.45),
            inset 0 0 18px rgba(254, 240, 138, 0.45) !important;
        z-index: 75 !important;
    }
    .pdf-hl-badge {
        position: absolute !important;
        top: -11px !important;
        left: 6px !important;
        background: #F59E0B !important;
        color: #FFFFFF !important;
        font-size: 0.72rem !important;
        font-weight: 800 !important;
        padding: 1px 7px !important;
        border-radius: 9999px !important;
        box-shadow: 0 2px 8px rgba(245, 158, 11, 0.5) !important;
        pointer-events: none !important;
        opacity: 0 !important;
        transition: opacity 0.15s ease !important;
        line-height: 1.2 !important;
    }
    .pdf-highlight-overlay:hover .pdf-hl-badge, 
    .pdf-highlight-overlay.active .pdf-hl-badge, 
    .pdf-highlight-overlay.pinned .pdf-hl-badge {
        opacity: 1 !important;
    }

    @keyframes luminous-glow-pulse {
        0%, 100% {
            box-shadow: 0 0 0 1.5px rgba(245, 158, 11, 0.40), 0 3px 14px rgba(245, 158, 11, 0.22), inset 0 0 10px rgba(254, 240, 138, 0.25);
        }
        50% {
            box-shadow: 0 0 0 2.5px rgba(245, 158, 11, 0.70), 0 5px 24px rgba(245, 158, 11, 0.40), inset 0 0 16px rgba(254, 240, 138, 0.40);
        }
    }
    .pdf-svg-container {
        width: 100% !important;
        display: block !important;
        line-height: 0 !important;
        user-select: text !important;
        -webkit-user-select: text !important;
    }
    .pdf-svg-container svg {
        width: 100% !important;
        height: auto !important;
        display: block !important;
    }

    /* Comparison Matrix Table Formatting */
    table {
        width: 100% !important;
        border-collapse: collapse !important;
        margin: 1rem 0 !important;
        font-size: 0.92rem !important;
        background: #FFFFFF !important;
        border-radius: 14px !important;
        overflow: hidden !important;
    }
    th {
        background-color: var(--ap-bg) !important;
        color: var(--ap-text) !important;
        font-weight: 700 !important;
        padding: 0.75rem 0.95rem !important;
        border-bottom: 1px solid #E8E4D8 !important;
    }
    td {
        padding: 0.7rem 0.95rem !important;
        border-bottom: 1px solid #E8E4D8 !important;
        vertical-align: top !important;
        line-height: 1.5 !important;
    }

    /* ------------------------------------------------------------- */
    /* 📐 KaTeX LaTeX Academic Formula Typography & Styling          */
    /* ------------------------------------------------------------- */
    .katex {
        font-size: 1.04em !important;
        font-family: KaTeX_Main, "KaTeX_Math", "Times New Roman", Times, serif !important;
        user-select: text !important;
        -webkit-user-select: text !important;
        line-height: 1.25 !important;
        text-rendering: auto !important;
    }
    .katex-display {
        margin: 0.85rem 0 !important;
        padding: 0.65rem 0.95rem !important;
        overflow-x: auto !important;
        overflow-y: hidden !important;
        background: rgba(0, 113, 227, 0.03) !important;
        border-radius: 12px !important;
        border: 1px solid rgba(0, 113, 227, 0.08) !important;
        text-align: center !important;
        max-width: 100% !important;
    }
    .katex-display > .katex {
        white-space: normal !important;
        text-align: center !important;
    }
    .katex .base {
        margin-top: 2px !important;
        margin-bottom: 2px !important;
    }
    .katex-error {
        color: #ef4444 !important;
        background: rgba(239, 68, 68, 0.08) !important;
        padding: 2px 4px !important;
        border-radius: 4px !important;
        font-size: 0.9em !important;
        font-family: ui-monospace, monospace !important;
    }

    /* ------------------------------------------------------------- */
    /* 🚀 7. Symmetrical Edge Page Navigation (Frosted Glass Buttons) */
    /* ------------------------------------------------------------- */

    /* Edge Navigation Hover Zones (Left: Previous Page, Right: Next Page) */
    /* ------------------------------------------------------------- */
    /* 🌐 12. Animated Translation Loader & Apple Moving UI           */
    /* ------------------------------------------------------------- */
    @keyframes spinOrbit {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    @keyframes pulseScale {
        0%, 100% { transform: scale(1); opacity: 0.9; }
        50% { transform: scale(1.08); opacity: 1; filter: drop-shadow(0 0 10px rgba(0, 113, 227, 0.45)); }
    }

    @keyframes shimmerFlow {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }

    @keyframes skeletonWave {
        0% { opacity: 0.5; background-position: -200% 0; }
        50% { opacity: 0.9; }
        100% { opacity: 0.5; background-position: 200% 0; }
    }

    @keyframes dotBounce {
        0%, 80%, 100% { transform: scale(0); opacity: 0.3; }
        40% { transform: scale(1); opacity: 1; }
    }

    /* Shimmer Bar */
    .shimmer-loader-bar {
        width: 100% !important;
        height: 4px !important;
        border-radius: 9999px !important;
        background: linear-gradient(90deg, #E8E4D8 0%, var(--ap-primary) 50%, #E8E4D8 100%) !important;
        background-size: 200% 100% !important;
        animation: shimmerFlow 1.6s infinite linear !important;
        margin: 0.6rem 0 !important;
    }

    /* Translation Loading Card Container */
    .translation-loading-card {
        background: rgba(255, 255, 255, 0.96) !important;
        backdrop-filter: blur(20px) !important;
        border: 1.5px solid rgba(0, 113, 227, 0.18) !important;
        border-radius: 20px !important;
        padding: 1.4rem 1.6rem !important;
        box-shadow: 0 12px 32px rgba(0, 113, 227, 0.08), 0 2px 8px rgba(0, 0, 0, 0.04) !important;
        margin-bottom: 1rem !important;
        position: relative !important;
        overflow: hidden !important;
    }

    .translation-loading-header {
        display: flex !important;
        align-items: center !important;
        gap: 0.9rem !important;
    }

    /* Moving Animated Translation Icon */
    .translation-spin-icon-box {
        width: 44px !important;
        height: 44px !important;
        border-radius: 14px !important;
        background: linear-gradient(135deg, var(--ap-primary) 0%, #87966A 100%) !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 14px rgba(0, 113, 227, 0.35) !important;
        animation: pulseScale 2.2s infinite ease-in-out !important;
        flex-shrink: 0 !important;
    }

    .translation-spin-icon-inner {
        animation: spinOrbit 3.5s infinite linear !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    .translation-loading-text-col {
        flex: 1 !important;
    }

    .translation-loading-title {
        font-size: 1.05rem !important;
        font-weight: 800 !important;
        color: var(--ap-text) !important;
        letter-spacing: -0.02em !important;
        display: flex !important;
        align-items: center !important;
        gap: 0.5rem !important;
        margin-bottom: 0.2rem !important;
    }

    .translation-loading-engine-badge {
        font-size: 0.76rem !important;
        font-weight: 700 !important;
        color: var(--ap-primary) !important;
        background: rgba(63, 89, 71, 0.1) !important;
        padding: 0.2rem 0.55rem !important;
        border-radius: 9999px !important;
    }

    .translation-loading-desc {
        font-size: 0.86rem !important;
        color: var(--ap-muted) !important;
        line-height: 1.4 !important;
    }

    /* Animated Dot Indicators */
    .loading-dots {
        display: inline-flex !important;
        align-items: center !important;
        gap: 3px !important;
        margin-left: 4px !important;
    }
    .loading-dots span {
        width: 4px !important;
        height: 4px !important;
        border-radius: 50% !important;
        background-color: var(--ap-primary) !important;
        display: inline-block !important;
        animation: dotBounce 1.4s infinite ease-in-out both !important;
    }
    .loading-dots span:nth-child(1) { animation-delay: -0.32s !important; }
    .loading-dots span:nth-child(2) { animation-delay: -0.16s !important; }
    .loading-dots span:nth-child(3) { animation-delay: 0s !important; }

    /* Translation Skeleton Placeholder Lines */
    .translation-skeleton-wrap {
        display: flex !important;
        flex-direction: column !important;
        gap: 0.75rem !important;
        margin-top: 1rem !important;
        padding-top: 0.9rem !important;
        border-top: 1px dashed rgba(0, 0, 0, 0.08) !important;
    }

    .translation-skeleton-line {
        height: 14px !important;
        border-radius: 6px !important;
        background: linear-gradient(90deg, #F0F0F2 25%, #E1E1E6 50%, #F0F0F2 75%) !important;
        background-size: 200% 100% !important;
        animation: skeletonWave 1.8s infinite ease-in-out !important;
    }

    .stButton button, .stFormSubmitButton button, .stDownloadButton button, [data-testid="stPopoverButton"] {
        min-height: 44px; border-radius: var(--ap-control-radius) !important;
    }
    [data-testid="stTextInput"] [data-baseweb="input"],
    [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stTextArea"] textarea {
        border-radius: var(--ap-control-radius) !important;
    }
    [data-testid="stPopoverBody"] { width: min(480px, calc(100vw - 24px)); max-width: calc(100vw - 24px); max-height: calc(100dvh - 32px); overflow-y: auto; background: var(--ap-surface); border-radius: 20px; }
    @media (max-width: 768px) {
        :root { --ap-page-gutter: 1rem; }
        .block-container { padding: 1rem 1rem 5rem !important; }
        .apple-store-title, .stApp h1 { font-size: 1.75rem; }
        [data-testid="stTabs"] [role="tab"] { white-space: nowrap; flex-shrink: 0; }
        .scrollable-trans-box { padding: 1rem; }
        .st-key-reader_toolbar [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.5rem !important; }
        .st-key-reader_toolbar [data-testid="stColumn"] { min-width: 0 !important; width: auto !important; flex: 1 1 0 !important; }
        .st-key-reader_toolbar button { width: 100%; padding-inline: 0.5rem; white-space: nowrap; }
        .st-key-reader_toolbar [data-testid="stCaptionContainer"] { white-space: nowrap; }
    }
    .st-key-reader_toolbar [data-testid="stCaptionContainer"] { text-align: center; margin-bottom: 0; }

    /* Reader edge arrows: sticky zero-height bar; each end is a hover zone at the main area's edge. */
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
    .st-key-reader_edge_prev button, .st-key-reader_edge_next button {
        width: 28px; min-width: 28px; height: 72px; padding: 0 !important; border-radius: 999px !important;
        background: rgba(255, 255, 255, 0.92) !important; border: 1px solid var(--ap-border) !important;
        box-shadow: 0 4px 16px rgba(32, 36, 44, 0.12); color: var(--ap-text) !important;
        opacity: 0; transition: opacity 150ms ease, background-color 150ms ease;
    }
    .st-key-reader_edge_prev button [data-testid="stMarkdownContainer"],
    .st-key-reader_edge_next button [data-testid="stMarkdownContainer"] {
        position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap;
    }
    .st-key-reader_edge_prev:hover button, .st-key-reader_edge_next:hover button,
    .st-key-reader_edge_prev button:focus-visible, .st-key-reader_edge_next button:focus-visible { opacity: 1; }
    .st-key-reader_edge_prev button:hover, .st-key-reader_edge_next button:hover {
        background: #EDF1E3 !important; color: var(--ap-primary) !important; border-color: var(--ap-primary) !important;
    }
    @media (hover: none) {
        .st-key-reader_edge_prev button, .st-key-reader_edge_next button { opacity: 0.75; }
    }
    .st-key-reader_edge_prev button:disabled, .st-key-reader_edge_next button:disabled { visibility: hidden !important; }
    @media (max-width: 640px) {
        .st-key-reader_edge_nav, [data-testid="stLayoutWrapper"]:has(> .st-key-reader_edge_nav) { display: none; }
    }
    .st-key-reader_toolbar [data-testid="stCaptionContainer"] p { margin: 0; }
    @media (prefers-reduced-motion: reduce) {
        .stApp *, .stApp *::before, .stApp *::after {
            animation: none !important; transition: none !important; scroll-behavior: auto !important;
        }
    }
</style>
"""
