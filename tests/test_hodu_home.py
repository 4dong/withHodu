"""Offline routing checks for the welcome screen and its persistent preferences."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class HoduHomeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # Essay navigation must never touch the user's real archive during tests.
        self.repo_patch = patch("ui.essay.workspace.DEFAULT_ESSAY_ARCHIVE_ROOT", Path(self.temp.name))
        self.repo_patch.start()
        self.addCleanup(self.repo_patch.stop)
        # The "continue reading" card comes from the paper archive; keep the user's reading record out.
        self.env_patch = patch.dict("os.environ", {"PAPER_ARCHIVE_ROOT": str(Path(self.temp.name) / "papers")})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()

    def back_home(self):
        next(button for button in self.at.button if button.label == "← 호두랑 시작 화면").click().run()

    def test_each_entry_routes_and_returns(self):
        for destination, expected in (("search", "학술 논문"), ("library", "학술 논문"), ("essay", "자기소개서")):
            with self.subTest(destination=destination):
                self.at.button(key=f"hodu_enter_{destination}").click().run()
                self.assertFalse(self.at.exception)
                self.assertEqual(self.at.session_state["current_workspace"], "essay" if destination == "essay" else "paper")
                self.assertEqual(self.at.button(key=f"sidebar_nav_{destination}").proto.type, "primary")
                if destination == "library":
                    self.assertIn("나의 서재", self.at.session_state["paper_navigation"])
                if destination == "search":
                    self.assertTrue(any("논문 검색</h1>" in m.value for m in self.at.markdown))
                self.back_home()
                self.assertFalse(self.at.exception)
                self.assertEqual(len(self.at.button), 3)

    def test_sidebar_buttons_switch_between_all_destinations(self):
        self.at.button(key="hodu_enter_search").click().run()
        for destination in ("library", "essay", "search"):
            self.at.button(key=f"sidebar_nav_{destination}").click().run()
            self.assertFalse(self.at.exception)
            self.assertEqual(self.at.session_state["current_workspace"],
                             "essay" if destination == "essay" else "paper")
            self.assertEqual(self.at.button(key=f"sidebar_nav_{destination}").proto.type, "primary")
            self.assertFalse(any(r.label in ("작업공간 선택", "탐색") for r in self.at.radio))
            if destination != "essay":
                self.assertIn("나의 서재" if destination == "library" else "논문 검색",
                              self.at.session_state["paper_navigation"])

    def test_essay_sections_live_in_the_sidebar(self):
        self.at.button(key="hodu_enter_essay").click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(len(self.at.tabs), 0)
        self.assertFalse(any("자기소개서 작업실" in m.value for m in self.at.markdown))
        self.assertEqual(self.at.button(key="essay_section_library").proto.type, "primary")

        self.at.button(key="essay_section_review").click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.button(key="essay_section_review").proto.type, "primary")
        headers = [m.value for m in self.at.markdown if "h-page-header" in m.value]
        self.assertEqual(len(headers), 1)
        self.assertIn("<h1>전사 검수</h1>", headers[0])
        # Hodu stays in empty and busy states, not beside page titles.
        self.assertNotIn("hodu-pose", headers[0])

        self.at.button(key="sidebar_nav_search").click().run()
        self.assertFalse(any(b.key == "essay_section_library" for b in self.at.button))

    def test_motion_preference_survives_round_trip(self):
        self.at.toggle(key="_hodu_reduce_motion").set_value(True).run()
        self.at.button(key="hodu_enter_search").click().run()
        self.back_home()
        self.assertTrue(self.at.toggle(key="_hodu_reduce_motion").value)

    def test_reader_is_offered_after_visiting_search(self):
        self.at.session_state["current_paper_bundle"] = {"pdf_path": "not-opened-in-this-test.pdf"}
        self.at.session_state["current_page_num"] = 7
        self.at.session_state["page_translations"] = {7: ["saved translation"]}
        self.at.run()
        self.assertTrue(any(b.label == "이어서 읽기 →" for b in self.at.button))
        self.at.button(key="hodu_enter_search").click().run()
        self.assertFalse(self.at.exception)
        self.back_home()
        self.assertTrue(any(b.label == "이어서 읽기 →" for b in self.at.button))
        saved = self.at.session_state["hodu_saved_reader"]
        self.assertEqual(saved["current_page_num"], 7)
        self.assertEqual(saved["page_translations"], {7: ["saved translation"]})


if __name__ == "__main__":
    unittest.main()
