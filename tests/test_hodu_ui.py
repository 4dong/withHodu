"""Offline checks for task-state cleanup, escaped copy, and workspace isolation."""

import tempfile
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from ui.hodu import state_html, walking_html


class HoduStateTests(unittest.TestCase):
    def test_user_content_is_escaped_and_status_is_semantic(self):
        markup = state_html('<script>alert(1)</script>', 'A & B', 'search', busy=True)
        self.assertNotIn('<script>', markup)
        self.assertIn('&lt;script&gt;', markup)
        self.assertIn('A &amp; B', markup)
        self.assertIn('role="status"', markup)
        self.assertIn('role="alert"', state_html('오류', tone='error'))

    def test_busy_states_use_their_frame_sheet_and_static_states_stay_still(self):
        for pose, animation in (("read", "reading-01"), ("search", "loading-walk-01"),
                                ("fetch", "loading-fetch-02")):
            markup = state_html("작업 중", pose=pose, busy=True)
            self.assertIn(f'data-hodu-animation="{animation}"', markup)
            self.assertNotIn('class="hodu-pose ', markup)
            self.assertNotIn('data-hodu-animation', state_html("완료", pose=pose))

    def test_loading_is_removed_on_exception(self):
        at = AppTest.from_string('''
import streamlit as st
from ui.hodu import loading, show_state
try:
    with loading("처리 중", "검증 자료", "read"):
        raise ValueError("controlled failure")
except ValueError:
    show_state("다시 시도해 주세요", "입력은 유지됩니다.", "think", "error")
''').run()
        self.assertFalse(at.exception)
        self.assertFalse(any('h-busy' in m.value for m in at.markdown))
        self.assertTrue(any('다시 시도해 주세요' in m.value for m in at.markdown))

    def test_essay_query_never_overwrites_paper_results(self):
        with tempfile.TemporaryDirectory() as directory:
            at = AppTest.from_string('''
import streamlit as st
from pathlib import Path
from unittest.mock import patch
from core.essay.repository import EssayRepository
from core.essay.embedding import MockEmbeddingProvider
from ui.essay.search_view import render_essay_search_view
from core.key_manager import KeyManager
st.session_state.setdefault("search_results", ["retained-paper-result"])
repo = EssayRepository(Path(''' + repr(directory) + '''))
with patch.object(KeyManager, "get_active_key", return_value=(None,None)), patch("ui.essay.search_view.get_active_embedding_provider", return_value=MockEmbeddingProvider()):
    render_essay_search_view(repo)
''', default_timeout=20).run()
            at.text_input[0].input('협업 경험').run()
            next(b for b in at.button if b.label == '검색').click().run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state['search_results'], ['retained-paper-result'])
            self.assertEqual(len(at.session_state['essay_search_results']), 2)
            # A subsequent widget rerun must still render the essay answer normally.
            at.expander[0]  # Search filters stay present alongside the answer.
            at.run()
            self.assertFalse(at.exception)


class PageTurnWalkTests(unittest.TestCase):
    def test_walk_label_is_escaped_status(self):
        markup = walking_html('<i>3</i>페이지')
        self.assertIn('&lt;i&gt;3&lt;/i&gt;페이지', markup)
        self.assertIn('role="status"', markup)
        self.assertIn('h-anim-loading-walk-01', markup)

    def test_walk_is_cleared_when_the_page_fails(self):
        at = AppTest.from_string('''
import streamlit as st
from ui.hodu import walking
slot = st.empty()
try:
    with walking("호두가 2페이지를 읽고 있어요", placeholder=slot):
        raise ValueError("controlled failure")
except ValueError:
    pass
''').run()
        self.assertFalse(at.exception)
        self.assertFalse(any('h-walk' in m.value for m in at.markdown))


class ThemeCssTests(unittest.TestCase):
    def test_theme_css_contains_no_markup(self):
        # st.html sanitizes the injected <style>; tag-like text anywhere in it drops the whole sheet.
        for name in ('hodu.css', 'home.css'):
            css = (Path(__file__).resolve().parents[1] / 'ui' / name).read_text(encoding='utf-8')
            self.assertNotRegex(css, r'<[/\w]', name)


if __name__ == '__main__':
    unittest.main()
