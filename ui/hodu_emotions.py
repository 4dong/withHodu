"""Home interaction states. Set animation to a manifest ID when new art is ready."""
import json
from pathlib import Path

from ui.hodu_animations import animation_html, animations, home_animation_html

EMOTIONS = {
    "idle": {"animation": None},
    "curious": {"animation": None},
    "happy": {"animation": None},
    "love": {"animation": None, "durationMs": 1100},
}


def emotion_html():
    assets = animations()
    layers = ''.join(
        f'<span class="h-emotion-frame" data-emotion-frame="{state}" hidden>'
        + animation_html(spec['animation'], variant='home') + '</span>'
        for state, spec in EMOTIONS.items() if spec['animation'] in assets
    )
    return ('<button type="button" class="h-emotion" data-emotion="idle" '
            'aria-label="호두 쓰다듬기" title="호두를 쓰다듬어 주세요">'
            '<span class="h-emotion-body" aria-hidden="true"><span class="h-emotion-default">'
            + home_animation_html() + '</span>' + layers + '</span>'
            '<span class="h-emotion-heart" aria-hidden="true">♥</span></button>')


def emotion_script(reduced=False):
    config = json.dumps({"reduced": bool(reduced), "states": EMOTIONS})
    return '<script>' + Path(__file__).with_suffix('.js').read_text().replace('__CONFIG__', config) + '</script>'
