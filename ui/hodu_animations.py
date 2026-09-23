"""Frame-based Hodu animation assets; CSS owns timing, no rerun/timer loop."""
import html
import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1] / 'assets/hodu/animations'
HOME_REST_MS = 16000
HOME_IDLE = 'home-idle-03'
BUSY_ANIMATIONS = {
    'search': 'loading-walk-01',
    'fetch': 'loading-fetch-02',
    'read': 'reading-01',
    'think': 'reading-01',
    'organize': 'loading-fetch-02',
}


@st.cache_data(show_spinner=False)
def _read_manifest(path, modified_ns):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def animations():
    path = ROOT / 'manifest.json'
    if not path.is_file():
        return {}
    return {a['id']: a for a in _read_manifest(str(path), path.stat().st_mtime_ns)['animations']}


def _position(a, frame):
    x = frame % a['columns'] * 100 / max(a['columns'] - 1, 1)
    y = frame // a['columns'] * 100 / max(a['rows'] - 1, 1)
    return f'{x:.6f}% {y:.6f}%'


def _keyframes(name, a, delay_ms=0):
    total = sum(a['durationsMs']) + delay_ms
    rules = [f'0%{{background-position:{_position(a, 0)};}}']
    elapsed = delay_ms
    for frame, duration in enumerate(a['durationsMs']):
        rules.append(f'{elapsed / total * 100:.6f}%{{background-position:{_position(a, frame)};}}')
        elapsed += duration
    rules.append(f'100%{{background-position:{_position(a, a["frameCount"] - 1)};}}')
    return f'@keyframes {name}{{{"".join(rules)}}}'


def animation_css():
    assets = animations()
    rules = []
    for name, a in assets.items():
        duration = sum(a['durationsMs'])
        repeat = 'infinite' if a.get('loop', True) else '1'
        rules.append(_keyframes(f'h-frames-{name}', a))
        rules.append(f'.h-anim-{name}{{background-size:{a["columns"] * 100}% {a["rows"] * 100}%;'
                     f'animation:h-frames-{name} {duration}ms steps(1,end) {repeat} both;}}')
    return '\n'.join(rules)


def animation_html(name, *, variant='portrait'):
    """Embed only the needed sheet; fall back to a matching static pose if missing."""
    # Local import avoids a module cycle with the shared Hodu UI helpers.
    from ui.hodu import _asset_data, portrait
    asset = animations().get(name)
    path = ROOT / asset['sheet'] if asset else None
    fallback = {'loading-walk-01': 'side', 'loading-fetch-02': 'fetch',
                'reading-01': 'read'}.get(name, 'front')
    if path is None or not path.is_file():
        return portrait(fallback)
    variant = variant if variant in {'portrait', 'walk', 'home'} else 'portrait'
    data = _asset_data(str(path), path.stat().st_mtime_ns)
    return (f'<div class="h-animation h-anim-{html.escape(name)} h-animation-{variant}" '
            f'data-hodu-animation="{html.escape(name)}" aria-hidden="true" '
            f'style="background-image:url(data:image/png;base64,{data})"></div>')


def home_animation_html():
    # Only one clock owns each action. Hidden idle restarts at its neutral first frame.
    return ('<div class="h-home-animation" aria-hidden="true">'
            '<div class="h-home-idle">' + animation_html(HOME_IDLE, variant='home') + '</div></div>')
