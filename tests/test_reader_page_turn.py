"""Page turns keep reader elements in place, so the previous page never lingers beside the new one."""

import re
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

# Offline reader: temporary archive, no stored keys, local stand-ins for PDF parsing and translation.
APP = '''
import os, runpy, sys, time
import streamlit as st
sys.path.insert(0, __ROOT__)
os.environ["ESSAY_ARCHIVE_ROOT"] = os.path.join(__ARCHIVE__, "essays")
app = runpy.run_path(os.path.join(__ROOT__, "app.py"), run_name="reader_page_turn_test")
import core.downloader
from core.key_manager import KeyManager
from core.parser import PaperPDFParser
from core.translator import PaperTranslator
from core.visual_highlighter import VisualHighlighter
core.downloader.DEFAULT_ARCHIVE_ROOT = os.path.join(__ARCHIVE__, "papers")
KeyManager.get_all_slots = classmethod(lambda cls: [])
KeyManager.get_active_key = classmethod(lambda cls, *args, **kwargs: ("", None))
FORMULA_ONLY = __FORMULA_ONLY__
FAILED_AGE = __FAILED_AGE__


def offline_page(cls, pdf_path, page_num, output_dir):
    text = f"Page {page_num} compares the method, the experiment, and the result."
    return {"page_num": page_num, "total_pages": 3, "stitched_prefix": "", "image_path": None,
            "blocks": [{"text": text, "bbox": {"top": "10%", "left": "8%", "width": "80%", "height": "6%"},
                        "kind": "equation" if FORMULA_ONLY else "text"}],
            "paragraphs": [text], "svg_content": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>'}


def offline_translation(cls, page_data, paper_title="", engine="", custom_api_key=None, custom_prompt=None):
    calls = st.session_state.setdefault("translation_calls", {})
    calls[page_data["page_num"]] = calls.get(page_data["page_num"], 0) + 1
    blocks = page_data["blocks"]
    if FORMULA_ONLY:
        pairs = [{"id": 1, "en": "", "ko": "", "kind": "equation", "bbox": blocks[0]["bbox"], "image_path": ""}]
    else:
        texts = [block["text"] for block in blocks]
        pairs = VisualHighlighter.align_translation_pairs(texts, ["번역 " + text for text in texts], blocks)
    result = {"page_num": page_data["page_num"], "engine": "offline", "is_fallback": False,
              "target_engine": engine, "pairs": pairs}
    if FAILED_AGE is not None:
        result.update(failed_count=1, failure_reason="offline failure", translated_at=time.time() - FAILED_AGE)
    return result


PaperPDFParser.get_single_page_data = classmethod(offline_page)
PaperTranslator.translate_single_page = classmethod(offline_translation)
if st.session_state.get("current_paper_bundle") is None:
    st.session_state.hodu_home = False
    st.session_state.current_page_num = 1
    st.session_state.page_translations = {}
    st.session_state.current_paper_bundle = {"pdf_path": "offline.pdf", "total_pages": 3, "metadata": {
        "id": "page-turn", "title": "Page turn fixture", "authors": ["Reader"], "year": 2026, "abstract": "",
        "venue": "", "citation_count": 0, "pdf_url": None, "doi": None, "source": "fixture", "url": "",
        "topic": "fixture"}}
app["main"]()
'''


def reader_positions(node, path=()):
    """Delta path of the translation pane and of each reader button."""
    found = {}
    children = getattr(node, "children", None)
    if isinstance(children, dict):
        for index, child in children.items():
            found.update(reader_positions(child, path + (index,)))
    value = getattr(node, "value", None)
    if isinstance(value, str) and re.search(r'id="trans-scroll-pane-\d+"', value):
        found["translation_pane"] = path
    key = getattr(node, "key", None)
    if type(node).__name__ == "Button" and key and key.startswith("reader_"):
        found[key] = path
    return found


def offline_app(archive, formula_only=False, failed_age=None):
    return (APP.replace("__ROOT__", repr(str(ROOT))).replace("__ARCHIVE__", repr(archive))
            .replace("__FORMULA_ONLY__", repr(formula_only)).replace("__FAILED_AGE__", repr(failed_age)))


class ReaderPageTurnTests(unittest.TestCase):
    def test_next_page_keeps_reader_positions_when_loading_is_skipped(self):
        # Page 1 is translated inside the run (loading state); page 2 comes from the prefetch
        # cache. Streamlit matches elements by position across reruns, so any shift leaves the
        # previous page's translation on screen until the run ends.
        with tempfile.TemporaryDirectory() as archive:
            at = AppTest.from_string(offline_app(archive), default_timeout=120).run()
            self.assertFalse(at.exception)
            first = reader_positions(at.main)
            self.assertIn(2, at.session_state["page_translations"], "page 2 should be prefetched")

            at.button(key="reader_next").click().run()
            self.assertFalse(at.exception)
            second = reader_positions(at.main)

        self.assertIn("translation_pane", first)
        self.assertEqual(first, second)


    def test_font_size_survives_page_turn_without_retranslation(self):
        with tempfile.TemporaryDirectory() as archive:
            at = AppTest.from_string(offline_app(archive), default_timeout=120).run()
            at.slider(key="reader_font_size").set_value(24).run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state["translation_calls"][1], 1)
            at.button(key="reader_next").click().run()
            self.assertFalse(at.exception)
            self.assertEqual(at.slider(key="reader_font_size").value, 24)
            panes = [m.value for m in at.markdown if 'id="trans-scroll-pane-' in m.value]
            self.assertTrue(panes)
            self.assertIn("font-size: 24px", panes[0])

    def test_page_holding_only_formulas_is_translated_once(self):
        # Formula pairs have no text to compare, yet the page counts as translated on the next rerun.
        with tempfile.TemporaryDirectory() as archive:
            at = AppTest.from_string(offline_app(archive, formula_only=True), default_timeout=120).run()
            at.run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state["translation_calls"][1], 1)

    def test_page_with_untranslated_paragraphs_is_translated_again_after_the_wait(self):
        with tempfile.TemporaryDirectory() as archive:
            at = AppTest.from_string(offline_app(archive, failed_age=120), default_timeout=120).run()
            self.assertTrue(any("번역하지 못해" in w.value for w in at.warning))
            at.run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state["translation_calls"][1], 2)

    def test_pages_read_before_come_back_without_translating_again(self):
        # The session forgets its translations (restart, another paper); the stored pages bring them back.
        with tempfile.TemporaryDirectory() as archive:
            at = AppTest.from_string(offline_app(archive), default_timeout=120).run()
            at.button(key="reader_next").click().run()
            self.assertEqual(at.session_state["translation_calls"], {1: 1, 2: 1, 3: 1})
            at.session_state["page_translations"] = {}
            at.run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state["translation_calls"], {1: 1, 2: 1, 3: 1})
            readings = list(Path(archive).glob("papers/*/*/reading.json"))
            self.assertEqual(len(readings), 1)
            self.assertIn('"last_page": 2', readings[0].read_text(encoding="utf-8"))

    def test_a_fresh_failure_is_not_requested_again_on_rerun(self):
        # Reruns within FAILED_PAGE_RETRY_SECONDS keep the partial page instead of hitting a limited service.
        with tempfile.TemporaryDirectory() as archive:
            at = AppTest.from_string(offline_app(archive, failed_age=0), default_timeout=120).run()
            at.run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state["translation_calls"][1], 1)


if __name__ == "__main__":
    unittest.main()
