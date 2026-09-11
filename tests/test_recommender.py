"""
Verification Test for Academic Searcher and Intent-Aware Recommendations
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.searcher import AcademicSearcher
from core.recommender import IntentRecommender

def test_search_and_recommendations():
    searcher = AcademicSearcher()
    papers = searcher.search("cosyvoice3", max_results=3)

    assert len(papers) > 0, "No papers found for query"
    top_paper = papers[0]
    assert "cosyvoice" in top_paper.title.lower(), f"Unexpected top paper title: {top_paper.title}"

    intent_data = IntentRecommender.analyze_and_recommend("cosyvoice3", papers)
    assert intent_data.get("inferred_intent") is not None
    assert intent_data.get("domain_tag") is not None
    assert len(intent_data.get("recommendations", [])) > 0, "No recommendations generated"

if __name__ == "__main__":
    test_search_and_recommendations()
    print("✅ Search and recommender tests passed.")
