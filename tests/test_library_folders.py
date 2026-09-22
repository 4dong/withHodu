import json
import tempfile
import unittest
from pathlib import Path
from core.downloader import ArchiveManager, DEFAULT_TOPIC
from core.searcher import Paper

class LibraryFoldersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.archive = ArchiveManager(self.tmp.name)
        self.paper = Paper('id', 'A paper title', ['Author'], 2026, '', '', 0, None, None, 'test', '')

    def test_new_paper_ignores_search_topic_and_reopen_preserves_move(self):
        path = self.archive.save_archive_bundle(self.paper.title, self.paper, None)
        self.assertEqual(Path(path).parent.name, DEFAULT_TOPIC)
        moved = self.archive.move_paper_topic(path, 'Speech AI')
        reopened = self.archive.save_archive_bundle('Another search', self.paper, None)
        self.assertEqual(moved, reopened)
        self.assertEqual(json.loads((Path(moved) / 'metadata.json').read_text())['topic'], 'Speech_AI')
        self.assertIn(DEFAULT_TOPIC, self.archive.list_archived_topics())
        self.assertEqual(len(self.archive.get_all_archived_papers()), 1)

    def test_default_survives_delete_and_invalid_moves_are_rejected(self):
        path = self.archive.save_archive_bundle('query', self.paper, None)
        for dest in ('!!!', '_reports'):
            with self.assertRaises(ValueError):
                self.archive.move_paper_topic(path, dest)
        self.archive.delete_paper(path)
        self.assertTrue((Path(self.tmp.name) / DEFAULT_TOPIC).is_dir())

    def test_collision_does_not_nest_or_lose_paper(self):
        path = self.archive.save_archive_bundle('query', self.paper, None)
        target = Path(self.tmp.name) / 'target' / Path(path).name
        target.mkdir(parents=True)
        with self.assertRaises(ValueError):
            self.archive.move_paper_topic(path, 'target')
        self.assertTrue((Path(path) / 'metadata.json').exists())

class LibraryInterfaceTest(unittest.TestCase):
    def test_create_folder_and_move_selection(self):
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as root:
            app = '''
import streamlit as st
from core.downloader import ArchiveManager
from core.searcher import Paper
from ui.library_view import render_library_view
a = ArchiveManager(ROOT)
if not a.get_all_archived_papers():
    a.save_archive_bundle('title search', Paper('id', 'Test paper', ['Author'], 2026, '', '', 0, None, None, 'test', ''), None)
render_library_view(a, {})
'''.replace('ROOT', repr(root))
            at = AppTest.from_string(app).run()
            def click(label):
                next(b for b in at.button if b.label == label).click().run()
                self.assertFalse(at.exception)
            self.assertFalse(at.exception)
            at.text_input[0].set_value('My research').run()
            click('폴더 만들기')
            self.assertEqual(at.selectbox[0].value, 'My_research')
            at.selectbox[0].select(DEFAULT_TOPIC).run()
            at.checkbox[0].check().run()
            next(s for s in at.selectbox if s.label == '이동할 폴더').select('My_research').run()
            click('선택한 논문 이동')
            self.assertEqual(at.session_state['selected_library_paper_paths'], [])
            at.selectbox[0].select('My_research').run()
            self.assertTrue(any(b.label == 'Test paper' for b in at.button))
            self.assertFalse(at.checkbox[0].value)
            at.text_input(key='library_query').set_value('no match').run()
            self.assertFalse(any(b.label == 'Test paper' for b in at.button))
            self.assertFalse(at.exception)
