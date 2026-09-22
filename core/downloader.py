"""
Paper Downloader and Local Archive Manager with Global Deduplication, Cover Generator & Live Disk Renaming
"""

import os
import re
import json
import shutil
import time
import base64
import urllib.parse
import xml.etree.ElementTree as ET
import requests
from typing import List, Dict, Any, Optional
from core.searcher import Paper

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

DEFAULT_TOPIC = "default"

DEFAULT_ARCHIVE_ROOT = os.path.expanduser("~/PaperArchive")

class ArchiveManager:
    """Manages local storage of academic papers with automatic deduplication, covers, and live file renaming."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = os.path.abspath(os.path.expanduser(base_dir or DEFAULT_ARCHIVE_ROOT))
        self.reports_dir = os.path.join(self.base_dir, "_reports")
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, DEFAULT_TOPIC), exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def _sanitize_folder_name(self, name: str) -> str:
        """Converts titles into safe, normalized folder names."""
        clean = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')
        return clean[:50]

    def find_existing_paper_dir(self, paper: Paper) -> Optional[str]:
        """Checks if the paper already exists in any topic folder across the archive."""
        safe_title = self._sanitize_folder_name(paper.title)
        expected_folder_name = f"{paper.year}_{safe_title}"

        if not os.path.exists(self.base_dir):
            return None

        for root, dirs, files in os.walk(self.base_dir):
            if "_reports" in root:
                continue
            for d in dirs:
                if d == expected_folder_name or (safe_title in d and str(paper.year) in d):
                    candidate_dir = os.path.join(root, d)
                    meta_path = os.path.join(candidate_dir, "metadata.json")
                    if os.path.exists(meta_path):
                        return candidate_dir
        return None

    def get_paper_dir(self, topic: str, paper: Paper) -> str:
        """
        Returns the paper directory path.
        If the paper is already saved in another topic, reuses the existing location to prevent duplication.
        """
        existing = self.find_existing_paper_dir(paper)
        if existing:
            return existing

        safe_topic = DEFAULT_TOPIC
        safe_title = self._sanitize_folder_name(paper.title)
        folder_name = f"{paper.year}_{safe_title}"
        return os.path.join(self.base_dir, safe_topic, folder_name)

    def download_pdf(self, paper: Paper, topic: str, timeout: int = 15) -> Optional[str]:
        """
        Downloads the PDF with multi-source fallback resolution (arXiv, Semantic Scholar, OpenReview).
        Reuses already downloaded PDF if valid.
        """
        paper_dir = self.get_paper_dir(topic, paper)
        os.makedirs(paper_dir, exist_ok=True)
        pdf_path = os.path.join(paper_dir, "paper.pdf")

        # 1. Reuse existing valid PDF
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1000:
            self.ensure_cover_thumbnail(paper_dir)
            return pdf_path

        # 2. Collect candidate PDF URLs
        candidate_urls = []
        if paper.pdf_url:
            candidate_urls.append(paper.pdf_url)

        # Check paper.url
        if paper.url:
            if "arxiv.org/abs/" in paper.url:
                ar_id = paper.url.split("/abs/")[-1].split("?")[0]
                candidate_urls.append(f"https://arxiv.org/pdf/{ar_id}.pdf")
            elif "openreview.net/forum?id=" in paper.url:
                or_id = paper.url.split("id=")[-1].split("&")[0]
                candidate_urls.append(f"https://openreview.net/pdf?id={or_id}")
            elif paper.url.endswith(".pdf"):
                candidate_urls.append(paper.url)

        # Try direct candidates
        for url in candidate_urls:
            if self._fetch_and_save_pdf(url, pdf_path, timeout):
                self.ensure_cover_thumbnail(paper_dir)
                return pdf_path

        # 3. Multi-Source Resolver: Search arXiv by title
        resolved_arxiv = self._resolve_arxiv_pdf_by_title(paper.title)
        if resolved_arxiv and self._fetch_and_save_pdf(resolved_arxiv, pdf_path, timeout):
            self.ensure_cover_thumbnail(paper_dir)
            return pdf_path

        # 4. Multi-Source Resolver: Search Semantic Scholar by title
        resolved_s2 = self._resolve_semantic_scholar_pdf_by_title(paper.title)
        if resolved_s2 and self._fetch_and_save_pdf(resolved_s2, pdf_path, timeout):
            self.ensure_cover_thumbnail(paper_dir)
            return pdf_path

        return None

    def _fetch_and_save_pdf(self, url: str, target_path: str, timeout: int) -> bool:
        """Fetches URL and saves if the response is a valid PDF."""
        try:
            resp = self.session.get(url, timeout=timeout, stream=True)
            if resp.status_code == 200:
                first_chunk = next(resp.iter_content(chunk_size=1024), b"")
                # Verify PDF magic header '%PDF'
                if b"%PDF" in first_chunk or resp.headers.get("content-type", "").startswith("application/pdf"):
                    with open(target_path, "wb") as f:
                        f.write(first_chunk)
                        for chunk in resp.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    if os.path.getsize(target_path) > 1000:
                        return True
        except Exception:
            pass
        return False

    def _resolve_arxiv_pdf_by_title(self, title: str) -> Optional[str]:
        """Queries arXiv API using paper title to resolve preprint PDF."""
        try:
            clean_q = " ".join(title.split()[:7])
            url = f"http://export.arxiv.org/api/query?search_query=all:{urllib.parse.quote(clean_q)}&max_results=2"
            resp = self.session.get(url, timeout=6)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                for entry in root.findall('atom:entry', ns):
                    id_url = entry.find('atom:id', ns).text.strip()
                    arxiv_id = id_url.split('/abs/')[-1]
                    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        except Exception:
            pass
        return None

    def _resolve_semantic_scholar_pdf_by_title(self, title: str) -> Optional[str]:
        """Queries Semantic Scholar Graph API for open-access PDF."""
        try:
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {"query": title, "limit": 1, "fields": "openAccessPdf,externalIds"}
            resp = self.session.get(url, params=params, timeout=6)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data:
                    item = data[0]
                    pdf_info = item.get("openAccessPdf")
                    if pdf_info and pdf_info.get("url"):
                        return pdf_info.get("url")
                    ar_id = (item.get("externalIds") or {}).get("ArXiv")
                    if ar_id:
                        return f"https://arxiv.org/pdf/{ar_id}.pdf"
        except Exception:
            pass
        return None

    def ensure_cover_thumbnail(self, paper_dir: str) -> Optional[str]:
        """Generates a high-quality 1st page visual thumbnail cover.png if not present."""
        if not fitz or not os.path.exists(paper_dir):
            return None

        cover_path = os.path.join(paper_dir, "cover.png")
        if os.path.exists(cover_path) and os.path.getsize(cover_path) > 1000:
            return cover_path

        pdf_path = os.path.join(paper_dir, "paper.pdf")
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1000:
            try:
                doc = fitz.open(pdf_path)
                if len(doc) > 0:
                    page = doc[0]
                    pix = page.get_pixmap(dpi=110)
                    pix.save(cover_path)
                doc.close()
                if os.path.exists(cover_path):
                    return cover_path
            except Exception as e:
                print(f"Cover generation error: {e}")
        return None

    def get_paper_cover_base64(self, paper_dir: str) -> Optional[str]:
        """Returns base64 data URI of the paper cover for ultra-fast browser rendering."""
        cover_path = self.ensure_cover_thumbnail(paper_dir)
        if cover_path and os.path.exists(cover_path):
            try:
                with open(cover_path, "rb") as cf:
                    encoded = base64.b64encode(cf.read()).decode("utf-8")
                    return f"data:image/png;base64,{encoded}"
            except Exception:
                pass
        return None

    def rename_paper(self, paper_dir: str, new_title: str) -> Optional[str]:
        """
        Live Filesystem Renamer:
        1. Updates title in metadata.json.
        2. Renames the actual physical folder on disk (~/PaperArchive/[topic]/[year_new_title]).
        3. Returns the newly renamed absolute folder path.
        """
        if not os.path.exists(paper_dir) or not new_title.strip():
            return None

        meta_path = os.path.join(paper_dir, "metadata.json")
        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, ValueError):
                meta = {}

        year = meta.get("year", 2025)
        clean_new_title = new_title.strip()
        safe_new_folder = f"{year}_{self._sanitize_folder_name(clean_new_title)}"
        
        parent_topic_dir = os.path.dirname(paper_dir)
        new_paper_dir = os.path.join(parent_topic_dir, safe_new_folder)

        # Update metadata fields
        meta["title"] = clean_new_title
        meta["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        meta["folder_path"] = new_paper_dir

        if new_paper_dir != paper_dir:
            try:
                # Rename actual directory on filesystem
                shutil.move(paper_dir, new_paper_dir)
            except Exception as e:
                print(f"Error moving folder on disk: {e}")
                # Fallback in-place write
                new_paper_dir = paper_dir

        # Write updated metadata to the new location
        new_meta_path = os.path.join(new_paper_dir, "metadata.json")
        with open(new_meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        return new_paper_dir

    def save_archive_bundle(self, topic: str, paper: Paper, pdf_path: Optional[str], 
                            bilingual_content: Optional[Dict[str, Any]] = None,
                            summary_md: Optional[str] = None,
                            visuals_data: Optional[Dict[str, Any]] = None) -> str:
        """Saves metadata, bilingual content, visuals, and summary report to the paper folder."""
        paper_dir = self.get_paper_dir(topic, paper)
        os.makedirs(paper_dir, exist_ok=True)

        meta_path = os.path.join(paper_dir, "metadata.json")
        meta_dict = paper.to_dict()
        meta_dict["topic"] = os.path.basename(os.path.dirname(paper_dir))
        meta_dict["has_pdf"] = bool(pdf_path and os.path.exists(pdf_path))
        meta_dict["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_dict, f, ensure_ascii=False, indent=2)

        if bilingual_content:
            bilingual_path = os.path.join(paper_dir, "bilingual.json")
            with open(bilingual_path, "w", encoding="utf-8") as f:
                json.dump(bilingual_content, f, ensure_ascii=False, indent=2)

        if summary_md:
            summary_path = os.path.join(paper_dir, "summary.md")
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary_md)

        if visuals_data:
            visuals_path = os.path.join(paper_dir, "visuals.json")
            with open(visuals_path, "w", encoding="utf-8") as f:
                json.dump(visuals_data, f, ensure_ascii=False, indent=2)

        self.ensure_cover_thumbnail(paper_dir)
        return paper_dir

    def load_paper_bundle(self, paper_dir: str) -> Dict[str, Any]:
        """Loads all artifacts associated with a paper from its local folder."""
        bundle = {
            "metadata": {},
            "pdf_path": os.path.join(paper_dir, "paper.pdf"),
            "cover_path": os.path.join(paper_dir, "cover.png"),
            "bilingual": None,
            "summary": None,
            "visuals": None,
            "images": []
        }

        meta_path = os.path.join(paper_dir, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                bundle["metadata"] = json.load(f)

        bilingual_path = os.path.join(paper_dir, "bilingual.json")
        if os.path.exists(bilingual_path):
            with open(bilingual_path, "r", encoding="utf-8") as f:
                bundle["bilingual"] = json.load(f)

        summary_path = os.path.join(paper_dir, "summary.md")
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                bundle["summary"] = f.read()

        visuals_path = os.path.join(paper_dir, "visuals.json")
        if os.path.exists(visuals_path):
            with open(visuals_path, "r", encoding="utf-8") as f:
                bundle["visuals"] = json.load(f)

        return bundle

    def list_archived_topics(self) -> List[str]:
        """Lists all topic directories in the archive (excluding system directories like _reports)."""
        if not os.path.exists(self.base_dir):
            return []
        topics = []
        for name in sorted(os.listdir(self.base_dir)):
            full_path = os.path.join(self.base_dir, name)
            if os.path.isdir(full_path) and not name.startswith(".") and name != "_reports":
                topics.append(name)
        return sorted(topics, key=lambda name: (name != DEFAULT_TOPIC, name))

    def list_papers_in_topic(self, topic: str) -> List[Dict[str, Any]]:
        """Lists all archived papers under a specific topic."""
        topic_dir = os.path.join(self.base_dir, topic)
        if not os.path.exists(topic_dir):
            return []

        papers = []
        for name in sorted(os.listdir(topic_dir)):
            paper_dir = os.path.join(topic_dir, name)
            if os.path.isdir(paper_dir) and not name.startswith("."):
                meta_path = os.path.join(paper_dir, "metadata.json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    meta["folder_path"] = paper_dir
                    meta["topic"] = topic
                    pdf_file = os.path.join(paper_dir, "paper.pdf")
                    meta["has_pdf"] = os.path.exists(pdf_file) and os.path.getsize(pdf_file) > 1000
                    if meta["has_pdf"]:
                        meta["pdf_size_mb"] = round(os.path.getsize(pdf_file) / (1024 * 1024), 2)
                    meta["cover_base64"] = self.get_paper_cover_base64(paper_dir)
                    papers.append(meta)
        return papers

    def get_all_archived_papers(self) -> List[Dict[str, Any]]:
        """
        ROOT Level Library Aggregator:
        Scans all topic directories across the entire repository and returns all papers.
        """
        all_papers = []
        topics = self.list_archived_topics()
        for t in topics:
            topic_papers = self.list_papers_in_topic(t)
            all_papers.extend(topic_papers)
        return all_papers

    def move_paper_topic(self, paper_dir: str, new_topic: str) -> Optional[str]:
        """Moves a paper folder from its current topic to a new topic folder."""
        if not os.path.exists(paper_dir):
            return None
        
        safe_topic = self._sanitize_folder_name(new_topic)
        if not safe_topic or safe_topic == "_reports":
            raise ValueError("사용할 수 없는 폴더 이름이에요.")
        target_topic_dir = os.path.join(self.base_dir, safe_topic)
        os.makedirs(target_topic_dir, exist_ok=True)

        folder_name = os.path.basename(paper_dir)
        new_paper_dir = os.path.join(target_topic_dir, folder_name)

        if new_paper_dir == paper_dir:
            return paper_dir

        if os.path.exists(new_paper_dir):
            raise ValueError("대상 폴더에 같은 이름의 논문이 있어요.")
        shutil.move(paper_dir, new_paper_dir)

        # Update metadata.json
        meta_path = os.path.join(new_paper_dir, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta["topic"] = safe_topic
            meta["folder_path"] = new_paper_dir
            meta["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

        # Clean old topic folder if empty
        old_topic_dir = os.path.dirname(paper_dir)
        if os.path.basename(old_topic_dir) != DEFAULT_TOPIC and os.path.exists(old_topic_dir) and not os.listdir(old_topic_dir):
            try:
                os.rmdir(old_topic_dir)
            except Exception:
                pass

        return new_paper_dir

    def delete_paper(self, paper_dir: str) -> bool:
        """Deletes a paper directory and cleans up empty parent topic folder."""
        if os.path.exists(paper_dir) and os.path.isdir(paper_dir):
            shutil.rmtree(paper_dir, ignore_errors=True)
            parent_topic = os.path.dirname(paper_dir)
            if os.path.basename(parent_topic) != DEFAULT_TOPIC and os.path.exists(parent_topic) and not os.listdir(parent_topic):
                try:
                    os.rmdir(parent_topic)
                except Exception:
                    pass
            return True
        return False

    # ------------------ Multi-Paper Comparison Reports Storage ------------------
    def save_comparison_report(
        self,
        title: str,
        paper_titles: List[str],
        report_markdown: str,
        engine_name: str = "Google Gemini 3.5 Flash"
    ) -> str:
        """Saves a multi-paper comparative analysis report to ~/PaperArchive/_reports/."""
        os.makedirs(self.reports_dir, exist_ok=True)
        report_id = f"report_{int(time.time())}_{self._sanitize_folder_name(title)[:20]}"
        report_folder = os.path.join(self.reports_dir, report_id)
        os.makedirs(report_folder, exist_ok=True)

        meta = {
            "id": report_id,
            "title": title,
            "papers": paper_titles,
            "paper_count": len(paper_titles),
            "engine": engine_name,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "folder_path": report_folder
        }

        with open(os.path.join(report_folder, "report.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        with open(os.path.join(report_folder, "report.md"), "w", encoding="utf-8") as f:
            f.write(report_markdown)

        return report_id

    def list_comparison_reports(self) -> List[Dict[str, Any]]:
        """Lists all saved multi-paper comparative analysis reports."""
        if not os.path.exists(self.reports_dir):
            return []
        reports = []
        for name in sorted(os.listdir(self.reports_dir), reverse=True):
            r_folder = os.path.join(self.reports_dir, name)
            if os.path.isdir(r_folder):
                json_path = os.path.join(r_folder, "report.json")
                if os.path.exists(json_path):
                    with open(json_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    reports.append(meta)
        return reports

    def get_comparison_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Loads a full comparison report (metadata + markdown)."""
        r_folder = os.path.join(self.reports_dir, report_id)
        if not os.path.exists(r_folder):
            return None

        json_path = os.path.join(r_folder, "report.json")
        md_path = os.path.join(r_folder, "report.md")

        meta = {}
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

        markdown = ""
        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                markdown = f.read()

        return {
            "meta": meta,
            "markdown": markdown
        }

    def delete_comparison_report(self, report_id: str) -> bool:
        """Deletes a comparison report folder."""
        r_folder = os.path.join(self.reports_dir, report_id)
        if os.path.exists(r_folder):
            shutil.rmtree(r_folder, ignore_errors=True)
            return True
        return False
