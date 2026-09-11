"""
Test Default Google Neural Translation with Academic Math Formatter Integration
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.translator import PaperTranslator
from core.math_formatter import AcademicMathFormatter

def test_default_google_neural_math_translation():
    # Academic paragraphs containing math equations
    dummy_page_data = {
        "page_num": 1,
        "paragraphs": [
            "We define the flow velocity field v_theta(x_t, t) with parameter theta and loss L(theta) = E[ || v_theta(x_t, t) - u ||^2 ].",
            "The discrete step uses Delta t interval with variance sigma^2 t^2(1 - t) and state variable x_t.",
            "The normalized advantage formula is ^Ai = (R(^xi 1, c) - mean{R}) / std{R}."
        ],
        "blocks": [
            {"text": "We define the flow velocity field v_theta(x_t, t) with parameter theta and loss L(theta) = E[ || v_theta(x_t, t) - u ||^2 ].", "bbox": {"top": "10%", "left": "10%", "width": "80%", "height": "20%"}},
            {"text": "The discrete step uses Delta t interval with variance sigma^2 t^2(1 - t) and state variable x_t.", "bbox": {"top": "35%", "left": "10%", "width": "80%", "height": "20%"}},
            {"text": "The normalized advantage formula is ^Ai = (R(^xi 1, c) - mean{R}) / std{R}.", "bbox": {"top": "60%", "left": "10%", "width": "80%", "height": "20%"}}
        ]
    }

    # 1. Translate using DEFAULT Google Neural Engine (Free Zero-Key)
    res = PaperTranslator.translate_single_page(
        page_data=dummy_page_data,
        paper_title="Flow Matching & Academic Math",
        engine="⚡️ Google Neural (무료 · 무제한)"
    )

    assert res is not None, "Translation returned None"
    assert "pairs" in res, "No pairs in result"
    assert len(res["pairs"]) == 3, f"Expected 3 pairs, got {len(res['pairs'])}"

    for pair in res["pairs"]:
        p_id = pair["id"]
        ko_text = pair["ko"]
        assert ko_text and len(ko_text.strip()) > 0, f"Pair {p_id} translation empty"

        # 2. Simulate UI rendering pipeline
        ko_formatted = AcademicMathFormatter.format_math_in_text(ko_text)
        ko_clean = AcademicMathFormatter.escape_html_outside_math(ko_formatted)

        assert ko_clean and len(ko_clean.strip()) > 0, f"Pair {p_id} HTML empty"
        print(f"[{p_id}] Translated & Normalized: {ko_clean}")

    print("✅ Default Google Neural translation + Math Formatter test passed successfully!")

if __name__ == "__main__":
    test_default_google_neural_math_translation()
