"""Asset extension and safe fallback contract for home emotions."""
import unittest
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


if __name__ == '__main__':
    unittest.main()
