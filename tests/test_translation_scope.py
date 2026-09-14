"""Reading order and translation scope: prose and formulas follow the PDF, while front matter,
tables, figures, captions and references stay untranslated."""

import tempfile
import unittest
from pathlib import Path

import fitz

from core.parser import PaperPDFParser
from core.visual_highlighter import VisualHighlighter

TITLE = "F5-TTS-RO: Extending F5-TTS to Romanian"  # repeated model names looked like a chart legend
AUTHORS = "Jane Reader and John Writer"
ABSTRACT = "This paper keeps translation focused on the prose readers need."
INTRO = "1 Introduction"
BODY_1 = "Speech models clone a voice from seconds of audio. We adapt one."
EQUATION = "h = ConvNeXt(E(x) + m), y = TTS(h)."
BODY_2 = "where E is the trainable embedding and m marks each character."
BODY_3 = "Training took twelve hours on one machine. It used one GPU and"
PAGE_2_BODY = "a batch of sixteen thousand audio frames."
APPENDIX = "A Implementation Details"
APPENDIX_BODY = "We list the settings used in every experiment."


def normalized(paragraphs):
    return [" ".join(p.split()) for p in paragraphs]


def build_paper(path):
    doc = fitz.open()

    def box(page, y0, text, size=10.5, center=False):
        overflow = page.insert_textbox(fitz.Rect(72, y0, 523, y0 + size * 2.2), text, fontsize=size,
                                       align=fitz.TEXT_ALIGN_CENTER if center else fitz.TEXT_ALIGN_LEFT)
        assert overflow >= 0, text

    first = doc.new_page(width=595, height=842)
    box(first, 60, TITLE, size=16, center=True)
    box(first, 100, AUTHORS, center=True)
    box(first, 130, "Abstract", size=11, center=True)
    box(first, 158, ABSTRACT)
    box(first, 190, INTRO, size=11)
    box(first, 218, BODY_1)
    box(first, 246, EQUATION, center=True)
    box(first, 272, BODY_2)
    box(first, 304, "Table 1: Training hyperparameters", center=True)
    for y in (332, 350, 404):  # booktabs-style rules only: find_tables alone misses this table
        first.draw_line(fitz.Point(150, y), fitz.Point(445, y), width=0.6)
    for y, (name, value) in ((346, ("Hyperparameter", "Value")), (366, ("Learning rate", "0.0001")),
                             (384, ("Steps", "40500")), (400, ("Batch size", "16384"))):
        first.insert_text(fitz.Point(160, y), name, fontsize=10)
        first.insert_text(fitz.Point(340, y), value, fontsize=10)
    box(first, 420, BODY_3)
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 32, 32), False)
    pixmap.set_rect(pixmap.irect, (210, 220, 230))
    first.insert_image(fitz.Rect(150, 470, 445, 630), pixmap=pixmap)
    first.insert_text(fitz.Point(250, 560), "Encoder block", fontsize=10)
    first.insert_text(fitz.Point(84, 550), "Utterance count", fontsize=9)  # axis title just outside the figure
    first.insert_text(fitz.Point(250, 642), "(a) Content consistency", fontsize=9)
    box(first, 648, "Figure 1: Overview of the model.", center=True)

    second = doc.new_page(width=595, height=842)
    box(second, 60, PAGE_2_BODY)
    for i, bar in enumerate((40, 55, 30, 62, 48, 36, 58, 44, 52, 38)):  # a vector bar chart with its axis titles
        x = 170 + i * 26
        second.draw_rect(fitz.Rect(x, 260 - bar, x + 16, 260), color=(0.2, 0.4, 0.6), fill=(0.6, 0.7, 0.8))
    second.draw_line(fitz.Point(160, 260), fitz.Point(440, 260), width=0.8)
    second.draw_line(fitz.Point(160, 190), fitz.Point(160, 260), width=0.8)
    second.insert_text(fitz.Point(300, 212), "in-domain", fontsize=8)
    second.insert_text(fitz.Point(270, 276), "Speaker ID", fontsize=9)
    box(second, 320, "References", size=11)
    box(second, 346, "[1] A. Author. A study of voices. In Proceedings, 2024.")
    box(second, 372, "[2] B. Author. Another study. arXiv, 2025.")

    third = doc.new_page(width=595, height=842)
    box(third, 60, "[3] C. Author. A third study. Journal, 2026.")
    box(third, 100, APPENDIX, size=11)
    box(third, 126, APPENDIX_BODY)
    doc.save(path)


class ReadingOrderTests(unittest.TestCase):
    def test_centred_formula_and_table_keep_a_single_column_page_in_order(self):
        # F5-TTS-RO page 3: width-based column detection moved the table ahead of the text above it.
        blocks = [
            (72.0, 290.6, 525.5, 328.6, "Figure 1: Overview"),
            (72.0, 346.5, 525.5, 414.1, "3.2.1 Code Switching"),
            (169.6, 429.9, 427.9, 442.6, "hR = ConvNeXt(ER(x) mR)"),
            (72.0, 449.0, 525.5, 487.3, "where ER is the trainable embedding"),
            (219.9, 503.2, 377.7, 515.8, "hcs = hR + hE"),
            (72.0, 522.5, 525.5, 560.5, "This approach is limited"),
            (72.0, 571.5, 137.0, 582.5, "3.3 Training"),
            (72.0, 589.1, 525.5, 613.6, "The training objective"),
            (223.2, 626.8, 374.3, 637.7, "Table 1: Training hyperparameters"),
            (122.7, 650.6, 345.3, 675.5, "Hyperparameter Value"),
            (122.7, 678.6, 332.0, 731.3, "Steps 40500"),
            (82.9, 754.7, 406.0, 765.6, "The training was executed"),
        ]
        self.assertEqual(VisualHighlighter.sort_blocks_by_reading_flow(blocks[::-1], 595.3), blocks)

    def test_two_column_page_reads_each_band_left_then_right(self):
        title = (50, 40, 550, 70, "title")
        left_a, right_a = (50, 90, 285, 250, "left a"), (315, 90, 550, 250, "right a")
        figure = (60, 270, 540, 420, "figure")
        left_b, right_b = (50, 440, 285, 700, "left b"), (315, 440, 550, 700, "right b")
        order = VisualHighlighter.sort_blocks_by_reading_flow([right_b, figure, left_a, title, right_a, left_b], 600)
        self.assertEqual([b[4] for b in order], ["title", "left a", "right a", "figure", "left b", "right b"])


class TranslationScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pdf = str(Path(cls.tmp.name, "paper.pdf"))
        build_paper(cls.pdf)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_first_page_keeps_title_abstract_headings_body_and_formulas_in_order(self):
        with fitz.open(self.pdf) as doc:
            _, paragraphs = VisualHighlighter.extract_aligned_page_blocks(doc[0])
        self.assertEqual(normalized(paragraphs), [TITLE, ABSTRACT, INTRO, BODY_1, EQUATION, BODY_2, BODY_3])

    def test_references_run_across_pages_until_the_appendix(self):
        with fitz.open(self.pdf) as doc:
            after_first = VisualHighlighter.references_state_after_page(doc[0])
            after_second = VisualHighlighter.references_state_after_page(doc[1], after_first)
            _, second = VisualHighlighter.extract_aligned_page_blocks(doc[1], in_references=after_first)
            _, third = VisualHighlighter.extract_aligned_page_blocks(doc[2], in_references=after_second)
        self.assertEqual((after_first, after_second), (False, True))
        self.assertEqual(normalized(second), [PAGE_2_BODY])
        self.assertEqual(normalized(third), [APPENDIX, APPENDIX_BODY])

    def test_panel_captions_are_captions_even_with_a_full_stop(self):
        self.assertTrue(VisualHighlighter._is_subfigure_caption("(a) Content Consistency."))
        self.assertFalse(VisualHighlighter._is_subfigure_caption("(a) We fine-tune the model on fifty speakers and evaluate it on held-out ones."))

    def test_author_notes_are_front_matter(self):
        self.assertTrue(VisualHighlighter.is_noise_or_meta("∗Work done during an internship at Google Brain."))

    def test_unfinished_sentence_continues_after_a_figure_on_the_next_page(self):
        with tempfile.TemporaryDirectory() as out:
            first = PaperPDFParser.get_single_page_data(self.pdf, 1, out)
            second = PaperPDFParser.get_single_page_data(self.pdf, 2, out)
        self.assertNotIn("Hyperparameter", " ".join(first["paragraphs"]))
        self.assertEqual(" ".join(first["paragraphs"][-1].split()), "Training took twelve hours on one machine.")
        self.assertEqual(second["stitched_prefix"], "It used one GPU and")
        self.assertEqual(normalized(second["paragraphs"]), [PAGE_2_BODY])


PROSE_BEFORE = "The path-wise gradients can then be computed as follows:"
PROSE_AFTER = "For example, the normal distribution can be re-written."


def build_formula_page(path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_textbox(fitz.Rect(72, 100, 523, 124), PROSE_BEFORE, fontsize=10.5)
    # A display formula split the way TeX PDFs are: math-font pieces at different heights, then the number.
    page.insert_text(fitz.Point(190, 160), "E[f(z)] =", fontname="symb", fontsize=11)
    page.insert_text(fitz.Point(252, 153), "df", fontname="symb", fontsize=9)
    page.insert_text(fitz.Point(252, 166), "dq", fontname="symb", fontsize=9)
    page.insert_text(fitz.Point(272, 160), "E[g(q)]", fontname="symb", fontsize=11)
    page.insert_text(fitz.Point(495, 160), "(4)", fontsize=10.5)
    page.insert_textbox(fitz.Rect(72, 190, 523, 214), PROSE_AFTER, fontsize=10.5)
    doc.save(path)


class DisplayFormulaTests(unittest.TestCase):
    def test_formula_pieces_become_one_region_between_the_paragraphs(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = str(Path(tmp, "formula.pdf"))
            build_formula_page(pdf)
            with fitz.open(pdf) as doc:
                blocks, paragraphs = VisualHighlighter.extract_aligned_page_blocks(doc[0])
        self.assertEqual([b["kind"] for b in blocks], ["text", "equation", "text"])
        self.assertEqual(normalized([paragraphs[0], paragraphs[2]]), [PROSE_BEFORE, PROSE_AFTER])
        x0, _, x1, _ = blocks[1]["raw_rect"]
        self.assertLess(x0, 195)
        self.assertGreater(x1, 505)  # the equation number belongs to the formula

    def test_parser_saves_the_original_rendering_of_each_formula(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = str(Path(tmp, "formula.pdf"))
            build_formula_page(pdf)
            data = PaperPDFParser.get_single_page_data(pdf, 1, tmp)
            formula = next(b for b in data["blocks"] if b["kind"] == "equation")
            self.assertTrue(Path(formula["image_path"]).is_file())
            pixmap = fitz.Pixmap(formula["image_path"])
        self.assertGreater(pixmap.width, 3 * 300)
        self.assertLess(min(pixmap.samples), 128)  # ink, not an empty crop


if __name__ == "__main__":
    unittest.main()
