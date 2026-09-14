"""
Tests the Gemini Notebook upload folder: archived paper PDFs land in 논문/, essay documents in
자소서/[title].txt, and a rebuild removes files for items that left the archive while keeping
files the user added by hand.
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.downloader import ArchiveManager
from core.essay.models import Document, new_uuid
from core.essay.repository import EssayRepository
from core.notebook_export import ESSAYS_DIRNAME, MAX_NAME_BYTES, PAPERS_DIRNAME, build_notebook_folder, safe_file_stem


def _add_paper(archive_root: Path, topic: str, folder: str, title: str, with_pdf: bool = True) -> Path:
    paper_dir = archive_root / topic / folder
    paper_dir.mkdir(parents=True)
    (paper_dir / "metadata.json").write_text(json.dumps({"title": title}), encoding="utf-8")
    # A cover already present keeps the archive from rendering one out of the fake PDF.
    (paper_dir / "cover.png").write_bytes(b"0" * 2000)
    if with_pdf:
        (paper_dir / "paper.pdf").write_bytes(b"%PDF-1.4\n" + b"0" * 2000)
    return paper_dir


def _names(folder: Path):
    return sorted(p.name for p in folder.iterdir())


def test_safe_file_stem():
    assert safe_file_stem("CosyVoice 3: Towards in-the-wild", "논문") == "CosyVoice 3 - Towards in-the-wild"
    assert safe_file_stem("Encoder/Decoder? \"A|B\"", "논문") == "Encoder-Decoder AB"
    assert safe_file_stem("???", "논문") == "논문"

    long_stem = safe_file_stem("품질" * 200, "자소서")
    assert len(long_stem.encode("utf-8")) <= MAX_NAME_BYTES
    assert long_stem.startswith("품질")


def test_build_notebook_folder():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        papers_root = tmp / "papers"
        archive_mgr = ArchiveManager(base_dir=str(papers_root))
        repo = EssayRepository(str(tmp / "essays"))
        dest = tmp / "notebook"

        _add_paper(papers_root, "TTS", "2025_CosyVoice", "CosyVoice 3: Towards in-the-wild speech generation")
        singlish_dir = _add_paper(papers_root, "TTS", "2026_Singlish", "Singlish, Can or Not?")
        _add_paper(papers_root, "TTS", "2024_NoPdf", "Paper Without PDF", with_pdf=False)

        doc = repo.create_document(Document(id=new_uuid(), title="기아_품질본부", company="기아", division="품질본부", role="품질"))
        repo.create_answer(doc.id, 1, "지원동기를 기술하시오.", "품질을 최우선으로 생각합니다.", review_status="approved")
        dup = repo.create_document(Document(id=new_uuid(), title="기아_품질본부", company="기아", division="품질본부", role="SW 품질"))

        res = build_notebook_folder(archive_mgr, repo, dest_root=str(dest))
        assert res["papers"] == 2 and res["essays"] == 2
        assert res["skipped_papers"] == 1 and res["removed"] == 0

        assert _names(dest / PAPERS_DIRNAME) == [
            "CosyVoice 3 - Towards in-the-wild speech generation.pdf",
            "Singlish, Can or Not.pdf",
        ]
        essay_names = _names(dest / ESSAYS_DIRNAME)
        assert essay_names == ["기아_품질본부 (2).txt", "기아_품질본부.txt"]
        assert any("품질을 최우선으로 생각합니다." in (dest / ESSAYS_DIRNAME / n).read_text(encoding="utf-8") for n in essay_names)

        # Rebuilding with nothing changed removes nothing.
        assert build_notebook_folder(archive_mgr, repo, dest_root=str(dest))["removed"] == 0

        # Items that left the archive disappear; a file the user dropped in stays.
        (dest / PAPERS_DIRNAME / "내가 넣은 자료.pdf").write_bytes(b"mine")
        shutil.rmtree(singlish_dir)
        repo.delete_document(dup.id)

        res = build_notebook_folder(archive_mgr, repo, dest_root=str(dest))
        assert res["removed"] == 2
        assert _names(dest / PAPERS_DIRNAME) == [
            "CosyVoice 3 - Towards in-the-wild speech generation.pdf",
            "내가 넣은 자료.pdf",
        ]
        assert _names(dest / ESSAYS_DIRNAME) == ["기아_품질본부.txt"]
        assert "품질을 최우선으로 생각합니다." in (dest / ESSAYS_DIRNAME / "기아_품질본부.txt").read_text(encoding="utf-8")


if __name__ == "__main__":
    test_safe_file_stem()
    test_build_notebook_folder()
    print("✅ Notebook export tests passed.")
