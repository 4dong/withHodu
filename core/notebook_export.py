"""
Gemini Notebook Upload Folder: gathers archived paper PDFs and essay documents into one folder
so they can be bulk-uploaded as notebook sources.

~/NotebookArchive/
    ├── 논문/[논문 제목].pdf
    └── 자소서/[지원서 제목].txt
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.downloader import ArchiveManager
from core.essay.models import utc_now_iso
from core.essay.repository import EssayRepository

DEFAULT_NOTEBOOK_ROOT = os.path.expanduser(
    os.environ.get("NOTEBOOK_ARCHIVE_ROOT", "~/NotebookArchive")
)
PAPERS_DIRNAME = "논문"
ESSAYS_DIRNAME = "자소서"
MANIFEST_NAME = ".notebook_manifest.json"
MAX_NAME_BYTES = 200


def safe_file_stem(title: str, fallback: str) -> str:
    """Keeps the title readable (the notebook shows it as the source name) while dropping characters file systems reject."""
    stem = re.sub(r"\s*:\s*", " - ", title or "")
    stem = re.sub(r"[\\/]", "-", stem)
    stem = re.sub(r'[*?"<>|\x00-\x1f]', "", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    stem = stem.encode("utf-8")[:MAX_NAME_BYTES].decode("utf-8", errors="ignore").strip(" .")
    return stem or fallback


def _unique_name(stem: str, ext: str, used: set) -> str:
    # Compared case-insensitively because the default macOS file system treats A.pdf and a.pdf as one file.
    name = f"{stem}{ext}"
    n = 2
    while name.casefold() in used:
        name = f"{stem} ({n}){ext}"
        n += 1
    used.add(name.casefold())
    return name


def build_notebook_folder(
    archive_mgr: ArchiveManager,
    essay_repo: EssayRepository,
    dest_root: Optional[str] = None
) -> Dict[str, Any]:
    """
    Copies every archived paper PDF into 논문/ and writes every active essay document
    (current revisions) to 자소서/[title].txt. Files a previous build wrote for items that
    have since left the archive are removed; files the user added by hand are left alone.
    """
    root = Path(dest_root or DEFAULT_NOTEBOOK_ROOT).expanduser().resolve()
    papers_dir = root / PAPERS_DIRNAME
    essays_dir = root / ESSAYS_DIRNAME
    papers_dir.mkdir(parents=True, exist_ok=True)
    essays_dir.mkdir(parents=True, exist_ok=True)

    written: List[str] = []

    used_papers: set = set()
    skipped_papers = 0
    for meta in archive_mgr.get_all_archived_papers():
        if not meta.get("has_pdf"):
            skipped_papers += 1
            continue
        src = Path(meta["folder_path"]) / "paper.pdf"
        name = _unique_name(safe_file_stem(meta.get("title", ""), "논문"), ".pdf", used_papers)
        dest = papers_dir / name
        src_stat = src.stat()
        if not (dest.exists() and dest.stat().st_size == src_stat.st_size
                and int(dest.stat().st_mtime) == int(src_stat.st_mtime)):
            shutil.copy2(src, dest)
        written.append(f"{PAPERS_DIRNAME}/{name}")

    used_essays: set = set()
    for doc in essay_repo.list_documents(include_deleted=False):
        answers = essay_repo.get_answers_for_document(doc.id)
        name = _unique_name(safe_file_stem(doc.title, "자소서"), ".txt", used_essays)
        (essays_dir / name).write_text(essay_repo._generate_document_full_txt(doc, answers), encoding="utf-8")
        written.append(f"{ESSAYS_DIRNAME}/{name}")

    manifest_path = root / MANIFEST_NAME
    previous: List[str] = []
    if manifest_path.exists():
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8")).get("files", [])
        except (json.JSONDecodeError, ValueError):
            previous = []

    current = {rel.casefold() for rel in written}
    removed = 0
    for rel in previous:
        stale = root / rel
        if rel.casefold() in current or stale.parent not in (papers_dir, essays_dir):
            continue
        if stale.is_file():
            stale.unlink()
            removed += 1

    manifest_path.write_text(
        json.dumps({"files": written, "built_at": utc_now_iso()}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return {
        "root": str(root),
        "papers": len(used_papers),
        "essays": len(used_essays),
        "skipped_papers": skipped_papers,
        "removed": removed
    }


def reveal_folder(path: str) -> bool:
    """Opens the folder in Finder (or the platform file manager)."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif os.name == "nt":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False
