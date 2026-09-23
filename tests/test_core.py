"""
Integration Test for withHodu Core Modules
"""

import os
import sys
import shutil

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.searcher import AcademicSearcher
from core.downloader import ArchiveManager
from core.translator import PaperTranslator

@pytest.mark.network  # live Scholar/arXiv/Google; run with `pytest -m network`
def test_core_pipeline():
    # 1. Academic Search
    searcher = AcademicSearcher()
    papers = searcher.search("Autonomous AI Agent Architecture", max_results=2)
    assert len(papers) > 0, "No papers retrieved"

    top_paper = papers[0]

    # 3. Translation & LaTeX Normalization
    dummy_page_data = {
        "page_num": 1,
        "paragraphs": [
            "Autonomous agents powered by large language models have shown remarkable capabilities in multi-step planning and tool usage.",
            "In this work, we propose a loss function L(theta) = E[ || v_theta(x_t, t) - u ||^2 ] to optimize reasoning trajectories."
        ],
        "blocks": [
            {"text": "Autonomous agents powered by large language models have shown remarkable capabilities in multi-step planning and tool usage.", "bbox": {"top": "10%", "left": "10%", "width": "80%", "height": "20%"}},
            {"text": "In this work, we propose a loss function L(theta) = E[ || v_theta(x_t, t) - u ||^2 ] to optimize reasoning trajectories.", "bbox": {"top": "35%", "left": "10%", "width": "80%", "height": "20%"}}
        ]
    }

    page_trans = PaperTranslator.translate_single_page(dummy_page_data, top_paper.title)
    assert len(page_trans.get("pairs", [])) > 0, "Translation pairs empty"

    # 4. Archive Manager Save & Load
    test_dir = "./tests/temp_test_archive"
    archive_mgr = ArchiveManager(base_dir=test_dir)
    saved_dir = archive_mgr.save_archive_bundle(
        topic="AI Agents",
        paper=top_paper,
        pdf_path=None,
        bilingual_content=page_trans
    )
    assert os.path.exists(saved_dir)

    loaded_bundle = archive_mgr.load_paper_bundle(saved_dir)
    assert loaded_bundle["metadata"] is not None
    assert loaded_bundle["bilingual"] is not None


    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir, ignore_errors=True)

if __name__ == "__main__":
    test_core_pipeline()
    print("✅ Core pipeline tests passed.")
