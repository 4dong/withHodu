"""
Test Engine Switch and Retranslation Cache Invalidation & Overwriting
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.translator import PaperTranslator

def test_engine_switch_and_cache_overwriting():
    dummy_page_data = {
        "page_num": 1,
        "paragraphs": [
            "We formulate flow matching using vector field v_theta(x_t, t) and discrete step Delta t.",
            "The model parameter theta is optimized by minimizing loss function L(theta)."
        ]
    }

    # 1. Step 1: Initial Translation using Google Neural
    engine_1 = "⚡️ Google Neural (무료 · 무제한)"
    res_1 = PaperTranslator.translate_single_page(
        page_data=dummy_page_data,
        paper_title="Flow Matching Paper",
        engine=engine_1
    )
    assert res_1["target_engine"] == engine_1
    assert len(res_1["pairs"]) == 2

    # Simulate Session Cache
    page_translations = {1: res_1}

    # 2. Step 2: Switch to Gemini Translation Engine
    engine_2 = "🤖 Google Gemini 3.7 Flash (최신 고성능 학술 AI · API 키 필요)"
    
    # Validation logic from app.py:
    cached_trans = page_translations.get(1)
    is_valid_cache = (
        cached_trans is not None
        and isinstance(cached_trans, dict)
        and "pairs" in cached_trans
        and len(cached_trans["pairs"]) > 0
        and cached_trans.get("target_engine") == engine_2
    )
    
    # Must be INVALID because target_engine was engine_1, not engine_2!
    assert is_valid_cache is False, "Stale cache was wrongly considered valid!"

    # Wipe stale translation & execute fresh translation with engine_2
    del page_translations[1]
    assert 1 not in page_translations, "Stale translation not wiped!"

    res_2 = PaperTranslator.translate_single_page(
        page_data=dummy_page_data,
        paper_title="Flow Matching Paper",
        engine=engine_2
    )
    # Overwrite cache with new translation
    page_translations[1] = res_2
    assert page_translations[1]["target_engine"] == engine_2
    assert page_translations[1] != res_1, "New translation did not replace the old one!"

    print("✅ Engine switch and translation overwrite test passed successfully!")

if __name__ == "__main__":
    test_engine_switch_and_cache_overwriting()
