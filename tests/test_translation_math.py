"""Formulas in translations stay readable: parsing keeps LaTeX intact and the pane hands it to KaTeX."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fitz

from core.math_formatter import AcademicMathFormatter
from core.translator import PaperTranslator
from core.visual_highlighter import VisualHighlighter

SCREENSHOT_FORMULA = r"$$h_R = \text{ConvNeXt}(E_R(x) \odot m_R), \quad h_E = E_{\text{TTS}}(x \odot m_E),$$"
BBOX = {"top": "10%", "left": "10%", "width": "80%", "height": "10%"}


class GeminiResponseParsingTests(unittest.TestCase):
    def test_single_backslash_latex_is_repaired(self):
        # JSON reads \t \f \b \n \r as control characters, and \o is invalid JSON.
        raw = '{"p1": "$\\text{a} \\frac{1}{2} \\beta \\nabla \\rho$", "p2": "$x \\odot y$"}'
        self.assertEqual(PaperTranslator._keyed_translations(raw, ["p1", "p2"]),
                         [r"$\text{a} \frac{1}{2} \beta \nabla \rho$", r"$x \odot y$"])

    def test_valid_json_and_real_escapes_are_unchanged(self):
        raw = json.dumps({"p1": SCREENSHOT_FORMULA, "p2": '첫 줄\n둘째 줄 "인용"'}, ensure_ascii=False)
        self.assertEqual(PaperTranslator._keyed_translations(raw, ["p1", "p2"]),
                         [SCREENSHOT_FORMULA, '첫 줄\n둘째 줄 "인용"'])

    def test_truncated_response_keeps_complete_items(self):
        raw = '{"p1": "첫 문단 $x_t$", "p2": "둘째 문단", "p3": "셋째 문단이 잘'
        self.assertEqual(PaperTranslator._keyed_translations(raw, ["p1", "p2", "p3"]), ["첫 문단 $x_t$", "둘째 문단", ""])

    def test_undecodable_json_is_never_a_translation(self):
        self.assertIsNone(PaperTranslator._keyed_translations('{"p1": oops}', ["p1"]))

    def test_gemini_output_skips_google_transliteration_heuristics(self):
        pairs = [{"id": 1, "en": "source", "ko": r"로우 레벨에서 모델 A는 \(x \to y\)를 쓴다.", "bbox": BBOX}]
        page = {"page_num": 1, "blocks": [{"text": "source", "bbox": BBOX}]}
        with mock.patch.object(PaperTranslator, "_translate_with_gemini", return_value=(pairs, "gemini-test")):
            result = PaperTranslator.translate_single_page(
                page, engine=PaperTranslator.SUPPORTED_ENGINES[1], custom_api_key="k" * 20)
        self.assertEqual(result["pairs"][0]["ko"], r"로우 레벨에서 모델 A는 $x \to y$를 쓴다.")


class MathFormatterTests(unittest.TestCase):
    def test_unicode_symbols_stay_readable_text(self):
        text = "입력 → 출력, 2 × 2 행렬, MSE·교차 엔트로피"
        self.assertEqual(AcademicMathFormatter.format_math_in_text(text), text)

    def test_neighbouring_formulas_are_not_merged(self):
        text = "두 좌표 $x$ $y$를 받는다."
        self.assertEqual(AcademicMathFormatter.format_math_in_text(text), text)


class TranslationPaneMarkdownTests(unittest.TestCase):
    def test_display_formula_gets_its_own_block(self):
        self.assertEqual(AcademicMathFormatter.to_markdown(SCREENSHOT_FORMULA),
                         "$$\n" + SCREENSHOT_FORMULA[2:-2] + "\n$$")

    def test_prose_is_literal_and_inline_math_is_kept(self):
        markdown = AcademicMathFormatter.to_markdown("표현 $h_R$는 *강조 아님* <b>태그</b> [링크](x) 비용 $5")
        self.assertIn("$h_R$는", markdown)
        self.assertIn(r"\*강조 아님\*", markdown)
        self.assertIn("&lt;b&gt;", markdown)
        self.assertIn(r"\[링크\]\(x\)", markdown)
        self.assertIn(r"\$5", markdown)

    def test_paragraph_body_is_markdown_between_html_lines(self):
        # Streamlit only renders math outside raw HTML blocks, so the div must end its line before the body.
        pane = VisualHighlighter.render_translation_paragraphs([{"id": 4, "ko": SCREENSHOT_FORMULA}], current_page=2)
        self.assertIn('id="para-item-4" data-id="4">\n\n<span class="doc-para-idx">[4]</span>\n\n$$\n', pane)
        self.assertIn("\n$$\n\n</div>", pane)


class DisplayFormulaPairTests(unittest.TestCase):
    def test_formulas_skip_translation_and_keep_their_place(self):
        page = {"page_num": 3, "blocks": [
            {"text": "Gradients follow:", "bbox": BBOX, "kind": "text"},
            {"text": "d/dq E f", "bbox": BBOX, "kind": "equation", "image_path": "/tmp/formula.png", "image_width_pt": 312.0},
            {"text": "For example, the normal distribution.", "bbox": BBOX, "kind": "text"},
        ]}

        def offline_google(texts, blocks, page_num, fallback_note=None):
            pairs = VisualHighlighter.align_translation_pairs(texts, ["번역: " + t for t in texts], blocks)
            return {"page_num": page_num, "engine": "offline", "pairs": pairs}

        with mock.patch.object(PaperTranslator, "_translate_with_google", side_effect=offline_google) as google:
            result = PaperTranslator.translate_single_page(page, engine=PaperTranslator.SUPPORTED_ENGINES[0])
        self.assertEqual(google.call_args.args[0], ["Gradients follow:", "For example, the normal distribution."])
        self.assertEqual([p["id"] for p in result["pairs"]], [1, 2, 3])
        self.assertEqual([p.get("kind", "text") for p in result["pairs"]], ["text", "equation", "text"])
        self.assertEqual(result["pairs"][1]["image_path"], "/tmp/formula.png")

    def test_page_with_only_formulas_sends_no_translation_request(self):
        page = {"page_num": 12, "blocks": [{"text": "x = y", "bbox": BBOX, "kind": "equation", "image_path": "/tmp/f.png"}]}
        with mock.patch.object(PaperTranslator, "_translate_with_google") as google:
            result = PaperTranslator.translate_single_page(page, engine=PaperTranslator.SUPPORTED_ENGINES[0])
        google.assert_not_called()
        self.assertEqual(result["target_engine"], PaperTranslator.SUPPORTED_ENGINES[0])
        self.assertEqual([p["kind"] for p in result["pairs"]], ["equation"])

    def test_pane_shows_the_formula_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp, "formula.png")
            pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 4), False)
            pixmap.clear_with(255)
            pixmap.save(str(image))
            pane = VisualHighlighter.render_translation_paragraphs(
                [{"id": 1, "ko": "앞 문단"}, {"id": 2, "kind": "equation", "image_path": str(image), "image_width_pt": 100}],
                current_page=3)
        self.assertIn('id="para-item-2"', pane)
        self.assertIn('<img class="doc-formula-image" src="data:image/png;base64,', pane)
        self.assertIn('style="width:150px"', pane)
        missing = VisualHighlighter.render_translation_paragraphs(
            [{"id": 1, "kind": "equation", "image_path": "/nonexistent/formula.png"}], current_page=3)
        self.assertIn("수식 이미지를 불러오지 못했어요", missing)


if __name__ == "__main__":
    unittest.main()
