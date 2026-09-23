"""Asset extension and safe fallback contract for home emotions."""
import unittest
import json
from PIL import Image
from ui.hodu_animations import ROOT, HOME_IDLE
from unittest.mock import patch

from ui import hodu_emotions


def frame(asset, index):
    """One frame cut from the runtime sprite sheet (the per-frame PNGs live in the hodu-art-v1 release)."""
    w, h = asset['frameWidth'], asset['frameHeight']
    col, row = index % asset['columns'], index // asset['columns']
    with Image.open(ROOT / asset['sheet']) as sheet:
        return sheet.convert('RGBA').crop((col * w, row * h, col * w + w, row * h + h))


class HoduEmotionTests(unittest.TestCase):
    def test_missing_future_frames_keep_default_art(self):
        with patch.dict(hodu_emotions.EMOTIONS, {"happy": {"animation": "future-happy"}}):
            markup = hodu_emotions.emotion_html()
        self.assertIn('class="h-emotion-default"', markup)
        self.assertNotIn('data-emotion-frame="happy"', markup)
        self.assertIn('aria-label="호두 쓰다듬기"', markup)

    def test_registered_frames_can_be_added_without_changing_controller(self):
        with patch.dict(hodu_emotions.EMOTIONS, {"happy": {"animation": "future-happy"}}), \
             patch.object(hodu_emotions, 'animations', return_value={"future-happy": {}}), \
             patch.object(hodu_emotions, 'animation_html', return_value='<span>frames</span>') as renderer:
            markup = hodu_emotions.emotion_html()
        self.assertIn('data-emotion-frame="happy" hidden', markup)
        renderer.assert_called_once_with('future-happy', variant='home')

    def test_action_endpoints_match_idle_pixels_and_geometry(self):
        assets = hodu_emotions.animations()
        reference = frame(assets[HOME_IDLE], 0)
        for name in (hodu_emotions.EMOTIONS['love']['animation'], hodu_emotions.EMOTIONS['shake']['animation']):
            asset = assets[name]
            self.assertEqual(asset['frameCount'], len(asset['durationsMs']))
            for index in (0, asset['frameCount'] - 1):
                endpoint = frame(asset, index)
                self.assertEqual(endpoint.size, reference.size)
                self.assertEqual(endpoint.tobytes(), reference.tobytes())

    def test_water_shake_preserves_every_original_pose(self):
        assets = hodu_emotions.animations()
        active = assets[hodu_emotions.EMOTIONS['shake']['animation']]
        self.assertEqual(active['preservedAnimation'], 'home-shake-02')
        start, end = active['preservedFrameRange']
        original = assets['home-shake-02']
        self.assertEqual(end-start+1, original['frameCount'])
        for offset in range(original['frameCount']):
            expected = Image.new('RGBA', (368,368))
            expected.alpha_composite(frame(original, offset).resize((391,391), Image.Resampling.NEAREST), (-23,-20))
            self.assertEqual(expected.tobytes(), frame(active, start + offset).tobytes())

    def test_controller_uses_actual_sprite_duration(self):
        script = hodu_emotions.emotion_script()
        config = json.loads(script.split('const config = ', 1)[1].split(';', 1)[0])
        for state in ('love', 'shake'):
            spec = config['states'][state]
            asset = hodu_emotions.animations()[spec['animation']]
            self.assertEqual(spec['durationMs'], sum(asset['durationsMs']))


if __name__ == '__main__':
    unittest.main()
