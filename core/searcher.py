"""
Google Scholar & Multi-Source Academic Paper Search Engine with Real-Time Exact Date Resolution
"""

import unicodedata
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup

@dataclass
class Paper:
    id: str
    title: str
    authors: List[str]
    year: int
    abstract: str
    venue: str
    citation_count: int
    pdf_url: Optional[str]
    doi: Optional[str]
    source: str
    url: str
    published_date: str = ""
    rank: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def get_formatted_date(self) -> str:
        """Returns formatted Korean date string like '2025년 5월 23일' or '2025년'."""
        if self.published_date:
            match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', self.published_date)
            if match:
                y, m, d = match.groups()
                return f"{y}년 {int(m)}월 {int(d)}일"
            match_m = re.match(r'^(\d{4})-(\d{1,2})', self.published_date)
            if match_m:
                y, m = match_m.groups()
                return f"{y}년 {int(m)}월"
            if len(self.published_date) == 4 and self.published_date.isdigit():
                return f"{self.published_date}년"
        return f"{self.year}년" if self.year else "최신 논문"


def normalize_title(title: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKC", title).casefold() if c.isalnum())


def titles_match(expected: str, found: str) -> bool:
    """Same paper title ignoring case and punctuation. Scholar may cut long titles with '…'."""
    expected = expected.strip()
    truncated = expected.endswith(("…", "..."))
    a = normalize_title(expected.rstrip(".… "))
    b = normalize_title(found)
    if not a:
        return False
    return a == b or (truncated and len(a) >= 20 and b.startswith(a))


class AcademicSearcher:
    """Multi-source academic search with exact-title promotion and date resolution."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def search(self, query: str, max_results: int = 8, sources: Optional[List[str]] = None) -> List[Paper]:
        """Search across providers, promoting exact titles before truncating results."""
        clean_q = query.strip()
        if not clean_q or max_results <= 0:
            return []
        results: List[Paper] = []
        seen_titles = set()

        # 1. Primary Organic Engine: Google Scholar
        try:
            scholar_results = self._search_google_scholar(clean_q, max_results=max_results)
            for p in scholar_results:
                norm_t = self._normalize_title(p.title)
                if norm_t not in seen_titles:
                    seen_titles.add(norm_t)
                    results.append(p)
        except Exception as e:
            print(f"Google Scholar search error: {e}")

        # A full-looking title needs verification even when Scholar returns many
        # loosely related papers. Result count alone is not evidence of a match.
        title_query = len(re.findall(r"[^\W_]+", clean_q)) >= 4

        def needs_fallback():
            return len(results) < min(3, max_results) or (
                title_query and not any(self._title_matches(clean_q, p.title) for p in results)
            )

        # 2. Fallback Engine: arXiv
        if needs_fallback():
            try:
                arxiv_results = self._search_arxiv_direct(clean_q, max_results=max_results)
                for p in arxiv_results:
                    norm_t = self._normalize_title(p.title)
                    if norm_t not in seen_titles:
                        seen_titles.add(norm_t)
                        results.append(p)
            except Exception as e:
                print(f"arXiv search error: {e}")

        # 3. Fallback Engine: Semantic Scholar
        if needs_fallback():
            try:
                s2_results = self._search_semantic_scholar(clean_q, max_results=max_results)
                for p in s2_results:
                    norm_t = self._normalize_title(p.title)
                    if norm_t not in seen_titles:
                        seen_titles.add(norm_t)
                        results.append(p)
            except Exception as e:
                print(f"Semantic Scholar search error: {e}")

        # Stable promotion: retain provider ordering among all other results.
        results.sort(key=lambda p: not self._title_matches(clean_q, p.title))
        final_papers = results[:max_results]

        # 4. Multi-Threaded Real-Time Date & PDF Enrichment Pipeline
        def enrich_paper(p: Paper) -> Paper:
            if len(p.published_date) >= 10 and p.pdf_url:
                return p
            exact_date, resolved_pdf = self._resolve_exact_date_and_pdf(p.url, p.title)
            if exact_date and len(exact_date) > len(p.published_date):
                p.published_date = exact_date
            if resolved_pdf and not p.pdf_url:
                p.pdf_url = resolved_pdf
            return p

        with ThreadPoolExecutor(max_workers=min(8, len(final_papers) or 1)) as executor:
            final_papers = list(executor.map(enrich_paper, final_papers))

        # Re-assign ranks 1..N
        for idx, p in enumerate(final_papers):
            p.rank = idx + 1

        return final_papers

    def _normalize_title(self, title: str) -> str:
        return normalize_title(title)

    def _title_matches(self, query: str, title: str) -> bool:
        normalized = self._normalize_title(query)
        return bool(normalized) and normalized == self._normalize_title(title)

    def _resolve_exact_date_and_pdf(self, url: str, title: str) -> tuple:
        """Resolves exact publication date (YYYY-MM-DD) and direct PDF via arXiv, CrossRef & HTML meta tags."""
        exact_date = ""
        resolved_pdf = ""

        # Step A: arXiv direct ID
        if url:
            ar_match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})', url)
            if ar_match:
                ar_id = ar_match.group(1)
                resolved_pdf = f"https://arxiv.org/pdf/{ar_id}.pdf"
                api_url = f"https://export.arxiv.org/api/query?id_list={ar_id}"
                try:
                    r = self.session.get(api_url, timeout=3.5)
                    if r.status_code == 200:
                        root = ET.fromstring(r.content)
                        ns = {'atom': 'http://www.w3.org/2005/Atom'}
                        entry = root.find('atom:entry', ns)
                        if entry is not None:
                            pub = entry.find('atom:published', ns)
                            if pub is not None and pub.text:
                                exact_date = pub.text.strip()[:10]
                                return exact_date, resolved_pdf
                except Exception:
                    pass

        # Step B: CrossRef API (IEEE, ACM, Springer, Nature, Science, Elsevier)
        try:
            clean_title = re.sub(r'[^a-zA-Z0-9\s]', ' ', title).strip()
            cr_url = f"https://api.crossref.org/works?query.bibliographic={urllib.parse.quote(clean_title[:80])}&rows=1"
            r = self.session.get(cr_url, timeout=3.5)
            if r.status_code == 200:
                data = r.json()
                items = data.get("message", {}).get("items", [])
                if items:
                    item = items[0]
                    cr_t = item.get("title", [""])[0].lower()
                    clean_cr = re.sub(r'[^a-zA-Z0-9]', '', cr_t)
                    clean_target = re.sub(r'[^a-zA-Z0-9]', '', title.lower())
                    if clean_target[:18] in clean_cr or clean_cr[:18] in clean_target:
                        dp = item.get("published-print") or item.get("published-online") or item.get("published") or item.get("created")
                        if dp:
                            parts = dp.get("date-parts", [[]])[0]
                            if len(parts) >= 3:
                                exact_date = f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
                            elif len(parts) >= 2:
                                exact_date = f"{parts[0]:04d}-{parts[1]:02d}"
                            elif len(parts) == 1:
                                exact_date = f"{parts[0]:04d}"
                        if exact_date:
                            return exact_date, resolved_pdf
        except Exception:
            pass

        # Step C: arXiv Title Query Fallback
        try:
            clean_q = " ".join(re.sub(r'[^a-zA-Z0-9\s]', '', title).split()[:6])
            api_url = f"https://export.arxiv.org/api/query?search_query=all:{urllib.parse.quote(clean_q)}&max_results=2"
            r = self.session.get(api_url, timeout=3.5)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                for entry in root.findall('atom:entry', ns):
                    t_found = entry.find('atom:title', ns).text
                    if titles_match(title, t_found):
                        pub = entry.find('atom:published', ns)
                        if pub is not None and pub.text:
                            exact_date = pub.text.strip()[:10]
                        id_url = entry.find('atom:id', ns).text.strip()
                        ar_id = id_url.split('/abs/')[-1]
                        resolved_pdf = f"https://arxiv.org/pdf/{ar_id}.pdf"
                        if exact_date:
                            return exact_date, resolved_pdf
        except Exception:
            pass

        # Step D: HTML Meta tags inspection (direct page landing)
        if url and url.startswith("http"):
            try:
                resp = self.session.get(url, timeout=3.0)
                if resp.status_code == 200:
                    html_txt = resp.text
                    m = re.search(r'<meta[^>]+(?:name|property)=[\"\'](?:citation_publication_date|citation_date|dc\.date|article:published_time)[\"\'][^>]+content=[\"\']([^\"\']+)[\"\']', html_txt, re.I)
                    if m:
                        raw = m.group(1).replace('/', '-')
                        d_m = re.search(r'(\d{4}-\d{1,2}-\d{1,2})', raw)
                        if d_m:
                            exact_date = d_m.group(1)
            except Exception:
                pass

        return exact_date, resolved_pdf

    def _search_google_scholar(self, query: str, max_results: int = 8) -> List[Paper]:
        """Scrapes and parses direct Google Scholar search page results."""
        papers = []
        encoded = urllib.parse.quote(query)
        url = f"https://scholar.google.com/scholar?q={encoded}&hl=ko"

        resp = self.session.get(url, timeout=8)
        if resp.status_code != 200:
            return papers

        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select('.gs_ri')

        for idx, item in enumerate(items[:max_results]):
            title_elem = item.select_one('.gs_rt')
            if not title_elem:
                continue

            clean_title = title_elem.get_text().replace('[HTML]', '').replace('[PDF]', '').replace('[B]', '').strip()
            link = title_elem.select_one('a')['href'] if title_elem.select_one('a') else ""

            snippet_elem = item.select_one('.gs_rs')
            abstract = snippet_elem.get_text().strip() if snippet_elem else "초록 정보를 불러오는 중..."

            pub_elem = item.select_one('.gs_a')
            pub_info = pub_elem.get_text().strip() if pub_elem else ""

            year_match = re.search(r'\b(19\d\d|20\d\d)\b', pub_info)
            year = int(year_match.group(1)) if year_match else 2024

            parts = pub_info.split(' - ')
            authors = [a.strip() for a in parts[0].split(',') if a.strip()] if parts else ["Researchers"]
            venue = parts[1].strip() if len(parts) > 1 else "Google Scholar Indexed"

            pdf_url = None
            if "arxiv.org/abs/" in link:
                arxiv_id = link.split("/abs/")[-1].split("?")[0]
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            elif link.endswith(".pdf"):
                pdf_url = link

            fl_elem = item.select_one('.gs_fl')
            cite_count = 0
            if fl_elem:
                cite_match = re.search(r'(\d+)회 인용|Cited by (\d+)', fl_elem.get_text())
                if cite_match:
                    cite_count = int(cite_match.group(1) or cite_match.group(2))

            papers.append(Paper(
                id=f"gs_{idx}_{self._normalize_title(clean_title)[:15]}",
                title=clean_title,
                authors=authors,
                year=year,
                published_date=str(year),
                abstract=abstract,
                venue=venue,
                citation_count=cite_count,
                pdf_url=pdf_url,
                doi=None,
                source="Google Scholar",
                url=link
            ))

        return papers

    def _search_arxiv_direct(self, query: str, max_results: int = 8) -> List[Paper]:
        """Queries arXiv API directly for preprint search."""
        papers = []
        ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
        # Escape punctuation into word boundaries and scope every term explicitly.
        # First retrieve titles, then search all fields when no title is found.
        terms = re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", query), re.UNICODE)
        if not terms:
            return papers
        for search_field in ("ti", "all"):
            params = {
                "search_query": " AND ".join(f'{search_field}:"{term}"' for term in terms),
                "start": 0, "max_results": max_results,
                "sortBy": "relevance", "sortOrder": "descending",
            }
            try:
                resp = self.session.get("https://export.arxiv.org/api/query", params=params, timeout=8)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.content)
                    for entry in root.findall('atom:entry', ns):
                        if entry.find('atom:published', ns) is not None:
                            papers.append(self._parse_arxiv_entry(entry, ns))
            except (requests.RequestException, ET.ParseError):
                continue
            if papers:
                break
        return papers

    def _parse_arxiv_entry(self, entry: ET.Element, ns: Dict[str, str]) -> Paper:
        id_url = entry.find('atom:id', ns).text.strip()
        arxiv_id = id_url.split('/abs/')[-1]
        title = entry.find('atom:title', ns).text.replace('\n', ' ').strip()
        summary = entry.find('atom:summary', ns).text.replace('\n', ' ').strip()
        published = entry.find('atom:published', ns).text.strip()
        published_date = published[:10] if published else ""
        year = int(published[:4]) if published else 2024
        
        authors = [a.find('atom:name', ns).text.strip() for a in entry.findall('atom:author', ns) if a.find('atom:name', ns) is not None and a.find('atom:name', ns).text]
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        
        doi_elem = entry.find('arxiv:doi', ns)
        doi = doi_elem.text.strip() if doi_elem is not None else None

        comment_elem = entry.find('arxiv:comment', ns)
        venue = "arXiv Preprint"
        if comment_elem is not None and comment_elem.text:
            venue = f"arXiv ({comment_elem.text[:25]}...)" if len(comment_elem.text) > 25 else f"arXiv ({comment_elem.text})"

        return Paper(
            id=f"arxiv_{arxiv_id}",
            title=title,
            authors=authors,
            year=year,
            published_date=published_date,
            abstract=summary,
            venue=venue,
            citation_count=0,
            pdf_url=pdf_url,
            doi=doi,
            source="arXiv",
            url=id_url
        )

    def _search_semantic_scholar(self, query: str, max_results: int = 5) -> List[Paper]:
        """Queries Semantic Scholar Graph API with exact publication dates."""
        papers = []
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": max_results,
            "fields": "paperId,title,authors,year,publicationDate,abstract,citationCount,venue,openAccessPdf,externalIds,url"
        }
        
        try:
            resp = self.session.get(url, params=params, timeout=8)
            if resp.status_code != 200:
                return papers

            data = resp.json()
            for item in data.get("data", []):
                if not item.get("title"):
                    continue
                
                authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
                pdf_info = item.get("openAccessPdf")
                pdf_url = pdf_info.get("url") if pdf_info else None
                
                ext_ids = item.get("externalIds") or {}
                doi = ext_ids.get("DOI")
                arxiv_id = ext_ids.get("ArXiv")
                if not pdf_url and arxiv_id:
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

                pub_date = item.get("publicationDate") or str(item.get("year") or "2024")

                papers.append(Paper(
                    id=f"s2_{item.get('paperId')}",
                    title=item.get("title", "").strip(),
                    authors=authors,
                    year=item.get("year") or 2024,
                    published_date=pub_date,
                    abstract=item.get("abstract") or "Abstract available in full text.",
                    venue=item.get("venue") or "Academic Conference / Journal",
                    citation_count=item.get("citationCount") or 0,
                    pdf_url=pdf_url,
                    doi=doi,
                    source="Semantic Scholar",
                    url=item.get("url") or (f"https://doi.org/{doi}" if doi else "")
                ))
        except Exception as e:
            print(f"Semantic Scholar error: {e}")
            
        return papers
