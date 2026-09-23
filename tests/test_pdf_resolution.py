"""Offline regressions: title-based PDF lookups must never return a different paper."""
from unittest.mock import Mock

from core.downloader import ArchiveManager
from core.searcher import titles_match


def feed(*entries):
    body = "".join(
        f"<entry><id>http://arxiv.org/abs/{arxiv_id}</id><title>{title}</title></entry>"
        for arxiv_id, title in entries
    )
    return f'<feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'.encode()


def manager(tmp_path, response):
    archive = ArchiveManager(str(tmp_path))
    archive.session.get = Mock(return_value=response)
    return archive


def test_titles_match_ignores_case_and_punctuation_only():
    assert titles_match("Attention is all you need", "Attention Is All You Need")
    assert titles_match("Finite Scalar Quantization VQ-VAE made simple",
                        "Finite Scalar Quantization: VQ-VAE Made Simple")
    assert not titles_match("Attention is all you need",
                            "Do You Even Need Attention? A Stack of Feed-Forward Layers")
    assert not titles_match("Attention is all you need", "Attention is All You Need in Speech Separation")


def test_titles_match_accepts_scholar_truncation():
    assert titles_match("Cosyvoice 3: Towards in-the-wild speech generation …",
                        "CosyVoice 3: Towards In-the-wild Speech Generation via Scaling-up and Post-training")
    assert not titles_match("Attention is all you need.", "Attention is All You Need in Speech Separation")


def test_arxiv_resolver_skips_other_papers(tmp_path):
    response = Mock(status_code=200, content=feed(
        ("2105.02723v1", "Do You Even Need Attention?"),
        ("1706.03762v7", "Attention Is All You Need"),
    ))
    archive = manager(tmp_path, response)
    assert archive._resolve_arxiv_pdf_by_title("Attention is all you need") == "https://arxiv.org/pdf/1706.03762v7.pdf"
    assert archive.session.get.call_args.kwargs["params"]["search_query"] == 'ti:"Attention is all you need"'


def test_arxiv_resolver_returns_none_without_match(tmp_path):
    response = Mock(status_code=200, content=feed(("2402.14810v1", "Some Other Diffusion Paper")))
    archive = manager(tmp_path, response)
    assert archive._resolve_arxiv_pdf_by_title("Denoising diffusion probabilistic models") is None


def test_semantic_scholar_resolver_checks_title(tmp_path):
    response = Mock(status_code=200)
    response.json.return_value = {"data": [
        {"title": "Unrelated", "openAccessPdf": {"url": "https://x/wrong.pdf"}},
        {"title": "Denoising Diffusion Probabilistic Models", "externalIds": {"ArXiv": "2006.11239"}},
    ]}
    archive = manager(tmp_path, response)
    assert archive._resolve_semantic_scholar_pdf_by_title("Denoising diffusion probabilistic models") \
        == "https://arxiv.org/pdf/2006.11239.pdf"


def test_landing_page_citation_pdf_url(tmp_path):
    page = '<html><head><meta name="citation_pdf_url" content="/paper/2020/file/abc-Paper.pdf"></head></html>'
    response = Mock(status_code=200, text=page, headers={"content-type": "text/html; charset=utf-8"},
                    url="https://proceedings.neurips.cc/paper/2020/hash/abc-Abstract.html")
    archive = manager(tmp_path, response)
    assert archive._resolve_landing_page_pdf(response.url) == "https://proceedings.neurips.cc/paper/2020/file/abc-Paper.pdf"
