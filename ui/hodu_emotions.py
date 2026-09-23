"""Home interaction states. Set animation to a manifest ID when new art is ready."""
import json
from pathlib import Path

from ui.hodu_animations import animation_html, animations, home_animation_html, HOME_REST_MS

EMOTIONS = {
    "idle": {"animation": None},
    "curious": {"animation": None},
    "happy": {"animation": None},
    "love": {"animation": "home-pet-02", "durationMs": 2000},
    "tickle": {"animation": None, "durationMs": 1400},
    "shake": {"animation": "home-shake-05", "durationMs": 4810},
}


def emotion_html():
    assets = animations()
    layers = ''.join(
        f'<span class="h-emotion-frame" data-emotion-frame="{state}" hidden>'
        + animation_html(spec['animation'], variant='home') + '</span>'
        for state, spec in EMOTIONS.items() if spec['animation'] in assets
    )
    return ('<div class="h-emotion" data-emotion="idle" role="group" '
            'aria-label="호두와 놀기" aria-describedby="hodu-touch-hint">'
            '<span class="h-emotion-body" aria-hidden="true"><span class="h-emotion-default">'
            + home_animation_html() + '</span>' + layers + '</span>'
            '<span class="h-emotion-heart" aria-hidden="true">♥</span>'
            '<span class="h-emotion-giggle" aria-hidden="true">♪</span>'
            '<button type="button" class="h-emotion-zone h-emotion-head" data-part="head" '
            'aria-label="호두 쓰다듬기" title="머리 쓰다듬기"></button>'
            '<button type="button" class="h-emotion-zone h-emotion-belly" data-part="belly" '
            'aria-label="호두 배 간지럽히기" title="배 간지럽히기"></button>'
            '<button type="button" class="h-emotion-zone h-emotion-tail" data-part="tail" '
            'aria-label="호두 꼬리 톡 건드리기" title="꼬리 톡 건드리기"></button>'
            '<span class="h-emotion-caption" id="hodu-touch-hint" role="status" '
            'aria-live="polite">머리·배·꼬리를 톡 눌러 보세요</span></div>')



def emotion_script(reduced=False):
    assets = animations()
    config = json.dumps({"reduced": bool(reduced), "states": {state: {**spec, "durationMs": sum(assets[spec["animation"]]["durationsMs"])}
                      if spec["animation"] in assets else spec
                      for state, spec in EMOTIONS.items()}, "restMs": HOME_REST_MS})
    return '<script>' + Path(__file__).with_suffix('.js').read_text(encoding='utf-8').replace('__CONFIG__', config) + '</script>'
