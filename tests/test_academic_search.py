"""Offline regressions for full-title retrieval and provider fallback."""
from unittest.mock import Mock

from core.searcher import AcademicSearcher, Paper

QUERY = 'Finite Scalar Quantization VQ-VAE made simple'
TITLE = 'Finite Scalar Quantization: VQ-VAE Made Simple'


def paper(title):
    return Paper(title, title, [], 2023, '', '', 0, 'https://arxiv.org/pdf/2309.15505',
                 None, 'arXiv', 'https://arxiv.org/abs/2309.15505', '2023-09-27')


def searcher(scholar, arxiv):
    s = AcademicSearcher()
    s._search_google_scholar = Mock(return_value=scholar)
    s._search_arxiv_direct = Mock(return_value=arxiv)
    s._search_semantic_scholar = Mock(return_value=[])
    return s


def test_related_scholar_results_do_not_hide_exact_title():
    s = searcher([paper(f'Related paper {i}') for i in range(8)], [paper(TITLE)])
    result = s.search(QUERY, max_results=5)
    assert result[0].title == TITLE
    assert len(result) == 5
    assert [p.rank for p in result] == list(range(1, 6))
    s._search_arxiv_direct.assert_called_once()
    s._search_semantic_scholar.assert_not_called()


def test_exact_scholar_match_avoids_unnecessary_fallback():
    s = searcher([paper(TITLE)], [])
    assert s.search(QUERY, max_results=1)[0].title == TITLE
    s._search_arxiv_direct.assert_not_called()


def test_short_topic_keeps_provider_order():
    original = [paper(f'Topic {i}') for i in range(5)]
    s = searcher(original, [])
    assert s.search('quantization', max_results=5) == original
    s._search_arxiv_direct.assert_not_called()


def test_semantic_fallback_still_runs_after_unrelated_arxiv_hits():
    s = searcher([paper(f'Related {i}') for i in range(5)], [paper('Other')])
    s._search_semantic_scholar.return_value = [paper(TITLE)]
    assert s.search(QUERY)[0].title == TITLE


def test_unicode_and_punctuation_normalization():
    s = AcademicSearcher()
    assert s._title_matches(QUERY, 'Finite Scalar Quantization: VQ–VAE Made Simple')
    assert s._normalize_title('한국어 논문') != s._normalize_title('다른 논문')


def test_empty_query_does_not_call_providers():
    s = searcher([], [])
    assert s.search('   ') == []
    assert s.search(QUERY, max_results=0) == []
    s._search_google_scholar.assert_not_called()


def test_arxiv_uses_scoped_terms_then_all_fields():
    s = AcademicSearcher()
    s.session.get = Mock(return_value=Mock(status_code=200, content=b'<feed xmlns="http://www.w3.org/2005/Atom"/>'))
    assert s._search_arxiv_direct(QUERY) == []
    first, second = s.session.get.call_args_list
    assert first.args[0].startswith('https://')
    assert first.kwargs['params']['search_query'] == ' AND '.join(
        f'ti:"{w}"' for w in ['Finite', 'Scalar', 'Quantization', 'VQ', 'VAE', 'made', 'simple'])
    assert second.kwargs['params']['search_query'].startswith('all:')
