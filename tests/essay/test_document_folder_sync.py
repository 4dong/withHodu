"""
Unit tests for Document-Centric Folder Synchronization.
Asserts that sync_document_folder creates dedicated document directories containing:
- [title].txt
- [title].md
- metadata.json
- images/[order]_[original_name]
"""

import io
import tempfile
from pathlib import Path
from PIL import Image

from core.essay.models import Document, new_uuid, utc_now_iso
from core.essay.repository import EssayRepository
from core.essay.ingest import EssayIngestService


def make_test_image(color="blue") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (60, 60), color=color).save(buf, format="JPEG")
    return buf.getvalue()


def test_document_folder_sync():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = EssayRepository(tmpdir)
        ingest_svc = EssayIngestService(repo)

        # 1. Ingest files
        img1 = make_test_image("red")
        img2 = make_test_image("blue")
        files = [
            ("cover_photo.jpg", img1, "image/jpeg"),
            ("q1_photo.jpg", img2, "image/jpeg")
        ]

        doc, sources, pages = ingest_svc.ingest_files(
            files=files,
            document_title="현대자동차_품질관리",
            company="현대자동차",
            division="품질본부",
            role="품질관리",
            collection="own_draft"
        )

        # Add an answer
        repo.create_answer(
            document_id=doc.id,
            question_number=1,
            question_text="지원동기를 기술하시오.",
            body_text="품질을 최우선으로 생각하는 엔지니어입니다.",
            origin="ocr",
            review_status="approved"
        )

        # 2. Synchronize document folder
        doc_dir = repo.sync_document_folder(doc.id)
        assert doc_dir is not None
        assert doc_dir.exists()

        # Check .txt file
        txt_files = list(doc_dir.glob("*.txt"))
        assert len(txt_files) == 1
        txt_content = txt_files[0].read_text(encoding="utf-8")
        assert "현대자동차" in txt_content
        assert "지원동기를 기술하시오" in txt_content
        assert "품질을 최우선으로" in txt_content

        # Check .md file
        md_files = list(doc_dir.glob("*.md"))
        assert len(md_files) == 1
        md_content = md_files[0].read_text(encoding="utf-8")
        assert "# [현대자동차]" in md_content

        # Check metadata.json
        meta_file = doc_dir / "metadata.json"
        assert meta_file.exists()

        # Check images directory
        images_dir = doc_dir / "images"
        assert images_dir.exists()
        images = list(images_dir.glob("*.jpg"))
        assert len(images) == 2
        assert any("cover_photo" in im.name for im in images)
        assert any("q1_photo" in im.name for im in images)

        print("✅ test_document_folder_sync passed successfully.")


if __name__ == "__main__":
    test_document_folder_sync()
