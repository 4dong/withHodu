"""
Unit Tests for VisualHighlighter Engine
Validates coordinate normalization, multi-column sorting, 1:1 pair alignment, and neon overlay rendering.
"""

import os
import sys
import unittest
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.visual_highlighter import VisualHighlighter
from core.math_formatter import AcademicMathFormatter


class MockRect:
    def __init__(self, x0, y0, x1, y1):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        self.width = x1 - x0
        self.height = y1 - y0


class TestVisualHighlighter(unittest.TestCase):

    def test_compute_relative_bbox(self):
        # 1. Pre-cropped canvas (0-origin from PyMuPDF page.set_cropbox)
        crop = MockRect(98, 40, 514, 722)  # width=416, height=682
        target_pre_cropped = MockRect(100, 200, 300, 400)  # already relative to (0,0)
        
        bbox = VisualHighlighter.compute_relative_bbox(target_pre_cropped, crop, pad_x=0.0, pad_y=0.0)
        self.assertIn("top", bbox)
        self.assertIn("left", bbox)
        self.assertIn("width", bbox)
        self.assertIn("height", bbox)
        
        # 100 / 416 = 24.04%
        self.assertEqual(bbox["left"], "24.04%")
        # 200 / 682 = 29.33%
        self.assertEqual(bbox["top"], "29.33%")
        # 200 / 416 = 48.08%
        self.assertEqual(bbox["width"], "48.08%")
        # 200 / 682 = 29.33%
        self.assertEqual(bbox["height"], "29.33%")

        # 2. Standard 0-origin crop box
        crop_zero = MockRect(0, 0, 1000, 1000)
        target_zero = MockRect(100, 200, 500, 400)
        bbox_zero = VisualHighlighter.compute_relative_bbox(target_zero, crop_zero, pad_x=0.5, pad_y=0.5)
        self.assertEqual(bbox_zero["left"], "9.50%")
        self.assertEqual(bbox_zero["top"], "19.50%")
        self.assertEqual(bbox_zero["width"], "41.00%")
        self.assertEqual(bbox_zero["height"], "21.00%")

    def test_sort_blocks_by_reading_flow_two_column(self):
        page_width = 600
        # Title spanning full page at y=50
        b_title = [50, 50, 550, 90, "Paper Title Spanning Full Width Header"]
        # Left col: block at y=100, block at y=200
        b_left_1 = [50, 100, 280, 180, "Left column paragraph 1"]
        b_left_2 = [50, 200, 280, 280, "Left column paragraph 2"]
        # Right col: block at y=100, block at y=200
        b_right_1 = [320, 100, 550, 180, "Right column paragraph 1"]
        b_right_2 = [320, 200, 550, 280, "Right column paragraph 2"]

        # Mix them up
        raw = [b_right_2, b_left_1, b_title, b_right_1, b_left_2]
        sorted_blocks = VisualHighlighter.sort_blocks_by_reading_flow(raw, page_width)

        # Expected order: Title -> Left 1 -> Left 2 -> Right 1 -> Right 2
        self.assertEqual(sorted_blocks[0][4], "Paper Title Spanning Full Width Header")
        self.assertEqual(sorted_blocks[1][4], "Left column paragraph 1")
        self.assertEqual(sorted_blocks[2][4], "Left column paragraph 2")
        self.assertEqual(sorted_blocks[3][4], "Right column paragraph 1")
        self.assertEqual(sorted_blocks[4][4], "Right column paragraph 2")

    def test_align_translation_pairs(self):
        en_texts = [
            "We propose a novel diffusion architecture.",
            "Our method achieves state-of-the-art results on ImageNet."
        ]
        ko_texts = [
            "우리는 새로운 디퓨전 아키텍처를 제안한다.",
            "우리 기법은 ImageNet에서 최고 성능을 달성한다."
        ]
        blocks = [
            {"bbox": {"top": "10%", "left": "5%", "width": "90%", "height": "15%"}},
            {"bbox": {"top": "30%", "left": "5%", "width": "90%", "height": "20%"}}
        ]

        pairs = VisualHighlighter.align_translation_pairs(en_texts, ko_texts, blocks)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0]["id"], 1)
        self.assertEqual(pairs[0]["en"], en_texts[0])
        self.assertEqual(pairs[0]["ko"], ko_texts[0])
        self.assertEqual(pairs[0]["bbox"]["top"], "10%")

        self.assertEqual(pairs[1]["id"], 2)
        self.assertEqual(pairs[1]["bbox"]["top"], "30%")

    def test_align_translation_pairs_fallback_count_mismatch(self):
        # Case: Translation returned fewer items
        en_texts = ["Sentence 1", "Sentence 2", "Sentence 3"]
        ko_texts = ["문장 1"]

        pairs = VisualHighlighter.align_translation_pairs(en_texts, ko_texts)
        self.assertEqual(len(pairs), 3)
        self.assertEqual(pairs[0]["ko"], "문장 1")
        # Fallback to English when Korean is missing
        self.assertEqual(pairs[1]["ko"], "Sentence 2")
        self.assertEqual(pairs[2]["ko"], "Sentence 3")

    def test_generate_single_overlay_html(self):
        bbox = {"top": "15.0%", "left": "10.0%", "width": "80.0%", "height": "12.0%"}
        html_out = VisualHighlighter.generate_single_overlay_html(pair_id=3, bbox=bbox)
        
        self.assertIn('id="pdf-hl-3"', html_out)
        self.assertIn('data-id="3"', html_out)
        self.assertIn('class="pdf-highlight-overlay"', html_out)
        self.assertIn('top:15.0%', html_out)
        self.assertIn('left:10.0%', html_out)
        self.assertIn('width:80.0%', html_out)
        self.assertIn('height:12.0%', html_out)
        # Event wiring is delegated: React rejects string event attributes (error #231).
        self.assertNotIn('onmouse', html_out)
        self.assertNotIn('onclick=', html_out)
        self.assertIn('<span class="pdf-hl-badge">[3]</span>', html_out)

    def test_render_overlay_canvas(self):
        pairs = [
            {"id": 1, "bbox": {"top": "10%", "left": "10%", "width": "80%", "height": "10%"}},
            {"id": 2, "bbox": {"top": "25%", "left": "10%", "width": "80%", "height": "15%"}}
        ]
        svg_mock = '<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="40"/></svg>'
        
        canvas_html = VisualHighlighter.render_overlay_canvas(
            pairs=pairs,
            current_page=1,
            svg_content=svg_mock
        )
        
        self.assertIn('class="unified-reader-frame"', canvas_html)
        self.assertIn('class="pdf-viewer-wrapper"', canvas_html)
        self.assertIn('class="pdf-content-canvas"', canvas_html)
        self.assertIn('id="pdf-hl-1"', canvas_html)
        self.assertIn('id="pdf-hl-2"', canvas_html)
        self.assertIn(svg_mock, canvas_html)

    def test_render_translation_paragraphs(self):
        pairs = [
            {"id": 1, "ko": "손실 함수 $\\mathcal{L}(\\theta)$를 최소화한다."},
            {"id": 2, "ko": "수렴 속도가 크게 향상된다."}
        ]
        
        pane_html = VisualHighlighter.render_translation_paragraphs(
            pairs=pairs,
            current_page=1,
            font_size=17,
            line_height=1.9
        )
        
        self.assertIn('id="para-item-1"', pane_html)
        self.assertIn('id="para-item-2"', pane_html)
        self.assertIn('font-size: 17px;', pane_html)
        self.assertIn('line-height: 1.9;', pane_html)
        self.assertIn('class="doc-para-idx">[1]</span>', pane_html)
        self.assertIn('class="doc-para-idx">[2]</span>', pane_html)

    def test_semantic_paragraph_merging_and_noise_filter(self):
        # Simulate Qwen paper Page 1 blocks: Header noise + Author List + Abstract Title + Body 1 + Body 2
        class MockPage:
            def __init__(self, rect, blocks):
                self.rect = rect
                self._blocks = blocks
            def get_text(self, kind):
                return self._blocks

        crop = MockRect(98, 40, 514, 722)
        mock_blocks = [
            (98, 45, 250, 60, "Alibaba Token Foundry\nDemo Page"),  # Noise header
            (98, 70, 514, 100, "(Equal contribution; alphabetical by given name.)\nBajian Xiang, Cheng Wen, Han Zhao, Hao Wang, Haoxu Wang, Jiawei Jin, Jiayan Cui, Jie Chen, Mengxi Nie, Tianyu Zhao, Weiqin Li, Xiang Lv, Xiangang Li, Yang Xiang, Yang Zhou"),  # Author metadata
            (180, 110, 240, 125, "Abstract"),  # Abstract Title (standalone)
            (98, 140, 514, 300, "In this report, we present Qwen-Audio-3.0-TTS, a production-oriented speech synthesis system that jointly advances content consistency, speaker similarity,"), # Abstract Part 1 (no period)
            (98, 305, 514, 450, "prosodic naturalness, audio quality, controllability, multilingual coverage, efficiency, and robustness. Across all evaluations, Qwen-Audio-3.0-TTS achieves state-of-the-art results.") # Abstract Part 2
        ]
        
        mock_page = MockPage(crop, mock_blocks)
        
        # Test noise filtering
        self.assertTrue(VisualHighlighter.is_noise_or_meta("Alibaba Token Foundry\nDemo Page"))
        self.assertTrue(VisualHighlighter.is_noise_or_meta(mock_blocks[1][4]))
        self.assertTrue(VisualHighlighter.is_noise_or_meta("Abstract"))

        # Test extraction pipeline
        blocks, paras = VisualHighlighter.extract_aligned_page_blocks(mock_page, crop_rect=crop)
        
        # Must extract exactly ONE clean merged Abstract paragraph (NOT containing authors)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(len(paras), 1)
        self.assertIn("In this report, we present Qwen-Audio-3.0-TTS", paras[0])
        self.assertNotIn("Bajian Xiang", paras[0])
        self.assertNotIn("Alibaba Token", paras[0])
        self.assertNotIn("Demo Page", paras[0])

        # BBox must span from Part 1 top (y=140) to Part 2 bottom (y=450)
        bbox = blocks[0]["bbox"]
        # top = (140 - 40) / (722 - 40) = 100 / 682 = 14.66%
        # height = (450 - 140) / 682 = 310 / 682 = 45.45%
        self.assertTrue(float(bbox["top"].replace("%", "")) < 20.0)
        self.assertTrue(float(bbox["height"].replace("%", "")) > 40.0)

    def test_page_7_math_formula_preservation(self):
        # Simulate Qwen paper Page 7: narrative intro + formula definition + formula line (1) + discussion
        class MockPage:
            def __init__(self, rect, blocks):
                self.rect = rect
                self._blocks = blocks
            def get_text(self, kind):
                return self._blocks

        crop = MockRect(98, 40, 514, 722)
        mock_blocks = [
            (98, 60, 514, 150, "We formulate the flow matching velocity prediction objective for speech synthesis as follows:"),
            (98, 160, 514, 230, "L(theta) = E[ || v_theta(x_t, t) - u(x_t, t) ||^2 ]    (1)"),  # Numbered formula block
            (98, 240, 514, 380, "where x_t is the interpolated state between noise and target speech, and u(x_t, t) is the target velocity vector field. During inference, we solve the SDE trajectory to synthesize high-fidelity audio.")
        ]

        mock_page = MockPage(crop, mock_blocks)
        blocks, paras = VisualHighlighter.extract_aligned_page_blocks(mock_page, crop_rect=crop)

        # Formula block (1) must NOT be filtered out
        self.assertEqual(len(blocks), 3)
        self.assertEqual(len(paras), 3)
        self.assertIn("L(theta)", paras[1])
        self.assertIn("(1)", paras[1])

        # Verify math formatting on the formula block
        formatted_math = AcademicMathFormatter.format_math_in_text(paras[1])
        self.assertIn("\\mathcal{L}", formatted_math)
        self.assertIn("(1)", formatted_math)

    def test_short_math_formula_preservation(self):
        class MockPage:
            def __init__(self, rect, blocks):
                self.rect = rect
                self._blocks = blocks
            def get_text(self, kind):
                return self._blocks

        crop = MockRect(0, 0, 500, 700)
        # Block with short math (length < 15)
        mock_blocks = [
            (50, 100, 450, 140, "We define the energy relation:"),
            (100, 150, 300, 170, "E = mc^2"),  # Short math (8 chars)
            (50, 180, 450, 220, "This formula explains mass-energy equivalence in relativistic physics.")
        ]
        mock_page = MockPage(crop, mock_blocks)
        blocks, paras = VisualHighlighter.extract_aligned_page_blocks(mock_page, crop_rect=crop)

        # All 3 blocks must be preserved (short math must NOT be dropped)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(len(paras), 3)
        self.assertEqual(paras[1], "E = mc^2")

    def test_figure_caption_preservation_and_chart_filtering(self):
        # Meaningful caption must NOT be filtered out as noise/chart
        caption_text = "Figure 2: Overview of the multi-head attention module and transformer layers."
        self.assertFalse(VisualHighlighter.is_figure_table_caption_or_chart(caption_text))

        # Pure numeric data series should be filtered
        chart_data = "84.2 19.5 0.94 12.8 55.3 91.0 42.1"
        self.assertTrue(VisualHighlighter.is_figure_table_caption_or_chart(chart_data))

        # Standalone subfigure label should be filtered
        self.assertTrue(VisualHighlighter.is_figure_table_caption_or_chart("(a)"))
        self.assertTrue(VisualHighlighter.is_figure_table_caption_or_chart("(b) baseline model"))

    def test_get_controller_assets(self):
        raw_js = VisualHighlighter.get_highlighter_js()
        self.assertIn('_agActivatePair', raw_js)
        self.assertIn('_agTogglePinPair', raw_js)

        assets = VisualHighlighter.get_controller_assets()
        self.assertIn('pdf-highlight-overlay', assets)
        self.assertIn('luminous-glow-pulse', assets)
        self.assertIn('<script>', assets)


if __name__ == "__main__":
    unittest.main()
