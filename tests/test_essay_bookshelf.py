"""Essay bookshelf: shelf grouping, spine labels, a random essay open by default that survives reruns, and deletion."""

import html
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.essay.models import Document, new_uuid
from core.essay.repository import EssayRepository
from ui.essay.library_view import OPEN_DOC_KEY, group_shelves, spine_key, spine_label

APP = '''
from pathlib import Path
from core.essay.repository import EssayRepository
from ui.essay.library_view import render_essay_library_view
render_essay_library_view(EssayRepository(Path({root!r})))
'''


def _doc(doc_id, title, company, collection="reference"):
    return Document(id=doc_id, title=title, company=company, division="", role="", collection=collection)


class BookshelfGroupingTests(unittest.TestCase):
    def test_shelves_follow_collection_order_then_company_then_title(self):
        shelves = group_shelves([
            _doc("1", "현대 품질", "현대"),
            _doc("2", "기아 품질본부", "기아"),
            _doc("3", "기아 국내생산", "기아"),
            _doc("4", "기아 초안", "기아", collection="own_draft"),
            _doc("5", "메모", "", collection="custom"),
        ])
        self.assertEqual([c for c, _ in shelves], ["own_draft", "reference", "custom"])
        reference = dict(shelves)["reference"]
        self.assertEqual([name for name, _ in reference], ["기아", "현대"])
        self.assertEqual([d.id for d in reference[0][1]], ["3", "2"])
        self.assertEqual(dict(shelves)["custom"][0][0], "기타")

    def test_spine_drops_the_company_the_bookend_already_shows(self):
        self.assertEqual(spine_label(_doc("1", "기아 KASO&QA 본부", "기아")), "KASO&QA 본부")
        self.assertEqual(spine_label(_doc("2", "기아_품질본부", "기아")), "품질본부")
        self.assertEqual(spine_label(_doc("3", "기아", "기아")), "기아")
        self.assertEqual(spine_label(_doc("4", "", "기아")), "제목 없음")

    def test_spine_key_is_stable_and_carries_tone_state_and_size(self):
        doc = _doc("abc-123", "기아 품질본부", "기아")
        key = spine_key(doc, approved=False)
        self.assertRegex(key, r"^essay_spine_t[0-5]_wait_h[0-3]_w[0-2]_abc-123$")
        self.assertEqual(key, spine_key(doc, approved=False))
        self.assertIn("_ok_", spine_key(doc, approved=True))


class BookshelfAppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = EssayRepository(self.temp.name)
        for division in ("품질본부", "국내생산"):
            doc = self.repo.create_document(Document(id=new_uuid(), title=f"기아 {division}", company="기아",
                                                     division=division, role=division,
                                                     notes="2026 홍길동\n[표지]: 기아\n\n합격 비결"))
            self.repo.create_answer(doc.id, 1, "지원 동기", f"{division} 본문입니다.\n\n둘째 문단", review_status="approved")
        self.at = AppTest.from_string(APP.format(root=self.temp.name), default_timeout=20)

    def tearDown(self):
        self.temp.cleanup()

    def _open_book_markdown(self):
        return [m.value for m in self.at.markdown if 'essay-book-title' in m.value or 'essay-answer' in m.value]

    def test_a_random_essay_opens_and_stays_open_across_reruns(self):
        self.at.run()
        self.assertFalse(self.at.exception)
        open_id = self.at.session_state[OPEN_DOC_KEY]
        self.assertIn(open_id, {d.id for d in self.repo.list_documents()})
        book = self._open_book_markdown()
        self.assertEqual(sum('essay-book-title' in m for m in book), 1)
        self.assertTrue(any('본문입니다.<br><br>둘째 문단' in m for m in book))
        self.assertTrue(any('2026 홍길동 [표지]: 기아<br>합격 비결' in m for m in book))

        self.at.run()
        self.assertEqual(self.at.session_state[OPEN_DOC_KEY], open_id)

    def test_clicking_a_spine_opens_that_essay(self):
        self.at.run()
        other = next(d for d in self.repo.list_documents() if d.id != self.at.session_state[OPEN_DOC_KEY])
        next(b for b in self.at.button if b.key and b.key.endswith(other.id)).click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.session_state[OPEN_DOC_KEY], other.id)
        self.assertTrue(any(html.escape(other.title) in m for m in self._open_book_markdown() if 'essay-book-title' in m))

    def test_deleting_the_open_essay_opens_another(self):
        self.at.run()
        open_id = self.at.session_state[OPEN_DOC_KEY]
        self.at.checkbox(key=f"del_confirm_{open_id}").check().run()
        self.at.button(key=f"del_{open_id}").click().run()
        self.assertFalse(self.at.exception)
        remaining = [d.id for d in self.repo.list_documents()]
        self.assertEqual(len(remaining), 1)
        self.assertEqual(self.at.session_state[OPEN_DOC_KEY], remaining[0])

    def test_empty_archive_shows_the_empty_shelf_state(self):
        with tempfile.TemporaryDirectory() as empty:
            at = AppTest.from_string(APP.format(root=empty), default_timeout=20).run()
            self.assertFalse(at.exception)
            self.assertTrue(any('책장이 비어' in m.value for m in at.markdown))


if __name__ == '__main__':
    unittest.main()
