"""
End-to-End Verification Test for withHodu Pipeline
"""

import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.searcher import AcademicSearcher
from core.verifier import PaperVerifier
from core.downloader import ArchiveManager
from core.parser import PaperPDFParser
from core.visual_extractor import PaperVisualExtractor
from core.translator import PaperTranslator
from core.qa_agent import PaperChatAgent

def test_full_e2e_pipeline():
    query = "Attention Is All You Need"  # open on arXiv; a paywalled top hit has no PDF to test with
    searcher = AcademicSearcher()
    papers = searcher.search(query, max_results=2)
    assert len(papers) > 0, "Failed to fetch papers"
    paper = papers[0]

    # Verification
    verified = PaperVerifier.verify_papers([paper], target_topic=query)
    top = verified[0]
    assert top.relevance_score > 0

    # Download
    test_archive_dir = "./tests/temp_test_e2e_archive"
    archive_mgr = ArchiveManager(base_dir=test_archive_dir)
    pdf_path = archive_mgr.download_pdf(top, "E2E_Test")
    assert pdf_path is not None and os.path.exists(pdf_path), "PDF download failed"

    # Visual extraction
    paper_dir = archive_mgr.get_paper_dir("E2E_Test", top)
    visuals = PaperVisualExtractor.extract_visuals(pdf_path, paper_dir, max_pages=2)
    assert len(visuals.get("page_screenshots", [])) > 0

    # Page 1 vector/data extraction
    page_1_data = PaperPDFParser.get_single_page_data(pdf_path, 1, paper_dir)
    assert page_1_data.get("image_path") and os.path.exists(page_1_data["image_path"])

    # Page 1 translation
    page_1_trans = PaperTranslator.translate_single_page(page_1_data, top.title)
    assert len(page_1_trans.get("pairs", [])) > 0

    # Chatbot QA
    chat_res = PaperChatAgent.answer_query(
        user_query="이 논문의 핵심 기여점 요약해줘",
        paper=top,
        current_page=1,
        page_texts=[p["ko"] for p in page_1_trans.get("pairs", [])]
    )
    assert chat_res.get("success") is True

    # Save and reload bundle
    archive_mgr.save_archive_bundle(
        topic="E2E_Test",
        paper=top,
        pdf_path=pdf_path,
        bilingual_content=page_1_trans,
        visuals_data=visuals
    )

    loaded_bundle = archive_mgr.load_paper_bundle(paper_dir)
    assert loaded_bundle["metadata"] is not None
    assert loaded_bundle["bilingual"] is not None

    # Cleanup
    if os.path.exists(test_archive_dir):
        shutil.rmtree(test_archive_dir, ignore_errors=True)

if __name__ == "__main__":
    test_full_e2e_pipeline()
    print("✅ E2E pipeline tests passed.")
