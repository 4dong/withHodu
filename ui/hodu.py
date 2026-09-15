"""Shared Hodu visual language, accessible task states, and motion preference."""

import base64
import html
from contextlib import contextmanager
from pathlib import Path

import streamlit as st

from ui.hodu_animations import animation_css, animation_html, BUSY_ANIMATIONS

ASSET = Path(__file__).resolve().parents[1] / "assets/hodu/hodu-pixel-transparent-v1.png"
SPINE_TEXTURE = Path(__file__).resolve().parents[1] / "assets/essay/book-spine.png"
POSES = {"front", "fetch", "read", "organize", "search", "think", "done", "rest", "side"}


@st.cache_data(show_spinner=False)
def _asset_data(path: str, modified_ns: int):
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def reference_data():
    return _asset_data(str(ASSET), ASSET.stat().st_mtime_ns)


def apply_theme():
    st.html('<style>' + Path(__file__).with_name('hodu.css').read_text(encoding='utf-8') + '\n' + animation_css() + '</style>')
    # A destination change starts at its heading; normal editing reruns keep scroll.
    navigation_epoch = int(st.session_state.get("hodu_navigation_epoch", 0))
    st.html(f"""<script>
    if (window.__hoduNavigationEpoch !== {navigation_epoch}) {{
        window.__hoduNavigationEpoch = {navigation_epoch};
        requestAnimationFrame(() => requestAnimationFrame(() => {{
            document.querySelector('[data-testid="stMain"]')?.scrollTo({{top:0, behavior:'instant'}});
        }}));
    }}
    </script>""", unsafe_allow_javascript=True)
    if ASSET.is_file():
        st.html('<style>.hodu-pose{background-image:url("data:image/png;base64,'
                + reference_data() + '")}</style>')
    if SPINE_TEXTURE.is_file():
        st.html('<style>.stApp{--spine-texture:url("data:image/png;base64,'
                + _asset_data(str(SPINE_TEXTURE), SPINE_TEXTURE.stat().st_mtime_ns) + '")}</style>')
    if st.session_state.get("hodu_motion_preference", False):
        st.html('<style>.stApp *, .stApp *::before, .stApp *::after '
                '{animation:none!important;transition:none!important;scroll-behavior:auto!important}</style>')


def remember_motion():
    st.session_state["hodu_motion_preference"] = st.session_state["_hodu_reduce_motion"]


def motion_toggle():
    if "_hodu_reduce_motion" not in st.session_state:
        st.session_state["_hodu_reduce_motion"] = st.session_state.get("hodu_motion_preference", False)
    return st.toggle("움직임 줄이기", key="_hodu_reduce_motion", on_change=remember_motion)


def portrait(pose="front", size="small"):
    pose = pose if pose in POSES else "think"
    size = size if size in {"small", "large", "tiny"} else "small"
    return (f'<div class="h-portrait h-portrait-{size}" aria-hidden="true">'
            f'<div class="hodu-pose hodu-{pose}"></div></div>')


def page_header(title, description=""):
    """Page title with an optional one-line description; Hodu appears only in empty and busy states."""
    detail = f'<p class="h-description">{html.escape(description)}</p>' if description else ''
    st.markdown(f'<header class="h-page-header"><h1>{html.escape(title)}</h1>{detail}</header>',
                unsafe_allow_html=True)


def state_html(title, detail="", pose="think", busy=False, tone="neutral"):
    tone = tone if tone in {"neutral", "success", "error", "empty"} else "neutral"
    role = 'status' if busy or tone == 'success' else ('alert' if tone == 'error' else 'note')
    artwork = animation_html(BUSY_ANIMATIONS.get(pose, 'loading-walk-01')) if busy else portrait(pose)
    return (f'<div class="h-state h-state-{tone}{" h-busy" if busy else ""}" role="{role}">'
            + artwork + '<div class="h-state-copy"><strong>' + html.escape(title)
            + '</strong><p>' + html.escape(detail) + '</p>'
            + ('<span class="h-working-track" aria-hidden="true"><i></i></span>' if busy else '')
            + '</div></div>')


def show_state(title, detail="", pose="think", tone="neutral"):
    st.markdown(state_html(title, detail, pose, tone=tone), unsafe_allow_html=True)


def walking_html(title):
    # The label comes first so Hodu walks over it; the strip itself ignores the pointer.
    return ('<div class="h-walk" role="status" aria-live="polite"><span class="h-walk-label">'
            + html.escape(title) + '</span><div class="h-walk-dog" aria-hidden="true">'
            + animation_html('loading-walk-01', variant='walk') + '</div></div>')


@contextmanager
def _transient(markup, placeholder=None):
    """Show markup until the block exits by success, failure, early return, or Streamlit rerun.

    When the wait is conditional, pass a placeholder created on every run so the element tree
    keeps its shape across reruns.
    """
    placeholder = st.empty() if placeholder is None else placeholder
    placeholder.markdown(markup, unsafe_allow_html=True)
    try:
        yield placeholder
    finally:
        placeholder.empty()


def loading(title, detail="", pose="read", placeholder=None):
    """Task state card with a working animation."""
    return _transient(state_html(title, detail, pose, busy=True), placeholder)


def walking(title, placeholder=None):
    """Page-turn wait: Hodu walks along the top edge of the window while the next page is prepared."""
    return _transient(walking_html(title), placeholder)


def sidebar_brand():
    st.markdown('<div class="h-sidebar-brand">' + portrait("front", "tiny")
                + '<div><strong>호두랑</strong><span>withHodu</span></div></div>', unsafe_allow_html=True)
