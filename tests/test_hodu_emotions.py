"""Asset extension and safe fallback contract for home emotions."""
import unittest
import json
from PIL import Image
from ui.hodu_animations import ROOT, HOME_IDLE
from unittest.mock import patch

from ui import hodu_emotions


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
        with Image.open(ROOT / assets[HOME_IDLE]['frames'][0]) as source:
            reference = source.convert('RGBA')
        for name in (hodu_emotions.EMOTIONS['love']['animation'], hodu_emotions.EMOTIONS['shake']['animation']):
            asset = assets[name]
            self.assertEqual(len(asset['frames']), len(asset['durationsMs']))
            for path in (asset['frames'][0], asset['frames'][-1]):
                with Image.open(ROOT / path) as frame:
                    self.assertEqual(frame.size, reference.size)
                    self.assertEqual(frame.convert('RGBA').tobytes(), reference.tobytes())

    def test_water_shake_preserves_every_original_pose(self):
        assets = hodu_emotions.animations()
        active = assets[hodu_emotions.EMOTIONS['shake']['animation']]
        self.assertEqual(active['preservedAnimation'], 'home-shake-02')
        start, end = active['preservedFrameRange']
        originals = assets['home-shake-02']['frames']
        self.assertEqual(end-start+1, len(originals))
        for source, target in zip(originals, active['frames'][start:end+1]):
            with Image.open(ROOT/source) as image:
                expected = Image.new('RGBA', (368,368))
                expected.alpha_composite(image.convert('RGBA').resize((391,391), Image.Resampling.NEAREST), (-23,-20))
            with Image.open(ROOT/target) as image:
                self.assertEqual(expected.tobytes(), image.convert('RGBA').tobytes())

    def test_controller_uses_actual_sprite_duration(self):
        script = hodu_emotions.emotion_script()
        config = json.loads(script.split('const config = ', 1)[1].split(';', 1)[0])
        for state in ('love', 'shake'):
            spec = config['states'][state]
            asset = hodu_emotions.animations()[spec['animation']]
            self.assertEqual(spec['durationMs'], sum(asset['durationsMs']))


if __name__ == '__main__':
    unittest.main()
