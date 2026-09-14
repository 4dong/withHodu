"""
Import View: Batch photo/PDF/text upload and document grouping.
"""

from __future__ import annotations
import streamlit as st
from ui.hodu import section_intro, show_state, loading, state_html
from pathlib import Path
from typing import List, Tuple

from core.essay.repository import EssayRepository
from core.essay.ingest import EssayIngestService
from core.essay.jobs import JobManager
from core.essay.transcription import get_active_ocr_provider, GeminiVisionOCRProvider, MockOCRProvider


def render_import_view(repo: EssayRepository):
    section_intro('자료 추가', '자기소개서 사진, PDF, 텍스트 파일을 올려 지원서 하나로 묶어 등록합니다.', '01 · 자료 모으기')

    ingest_svc = EssayIngestService(repo)

    with st.form("essay_import_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("지원서 제목", placeholder="예: 기아 품질본부 SW 품질 참고자료")
            company = st.text_input("기업명", placeholder="예: 기아, 현대자동차, 삼성전자")
            division = st.text_input("본부/사업부", placeholder="예: 품질본부, R&D본부")
        with col2:
            role = st.text_input("지원 직무", placeholder="예: SW 품질, 자율주행, 품질보증")
            collection = st.selectbox(
                "자료 구분",
                key="essay_import_collection",
                options=["reference", "own_draft", "own_experience", "recruitment_notice"],
                format_func=lambda x: {
                    "reference": "참고 자소서 (타인·선배)",
                    "own_draft": "내 자소서 초안",
                    "own_experience": "내 경험 정리",
                    "recruitment_notice": "채용·직무 공고"
                }.get(x, x)
            )
            notes = st.text_input("메모", placeholder="예: 2026 수집 참고자료, Q2 문항 누락")

        uploaded_files = st.file_uploader(
            "파일 선택 (JPG, PNG, WEBP, PDF, TXT, MD)",
            type=["jpg", "jpeg", "png", "webp", "pdf", "txt", "md"],
            accept_multiple_files=True
        )

        submitted = st.form_submit_button("등록하기", type="primary", use_container_width=True)

    if submitted:
        if not title.strip() or not company.strip() or not role.strip():
            st.error("지원서 제목, 기업명, 지원 직무는 필수 입력 항목입니다.")
            return

        if not uploaded_files:
            st.error("최소 1개 이상의 파일을 선택해 주세요.")
            return

        with loading("호두가 자료를 챙기고 있어요", "파일을 확인하고 지원서 하나로 묶어 보관해요.", "organize"):
            file_tuples: List[Tuple[str, bytes, str]] = []
            for up in uploaded_files:
                b = up.getvalue()
                mime = up.type or ""
                file_tuples.append((up.name, b, mime))

            try:
                doc, sources, pages = ingest_svc.ingest_files(
                    files=file_tuples,
                    document_title=title.strip(),
                    company=company.strip(),
                    division=division.strip(),
                    role=role.strip(),
                    collection=collection
                )
                if notes.strip():
                    doc.notes = notes.strip()
                    repo.update_document(doc)

                st.success(f"'{doc.title}'을(를) 등록했습니다. (원본 {len(sources)}개, {len(pages)}페이지)")

                # Enqueue OCR jobs for pages
                job_mgr = JobManager(repo)
                ocr_jobs = []
                for p in pages:
                    j = job_mgr.enqueue_ocr_job(doc.id, p.id)
                    ocr_jobs.append(j)

            except Exception as e:
                st.error(f"등록 실패: {e}")
                return

        # Immediate OCR execution if there are OCR jobs
        if ocr_jobs:
            ocr_provider = get_active_ocr_provider()
            provider_desc = "Gemini Vision AI" if isinstance(ocr_provider, GeminiVisionOCRProvider) else "오프라인 모의 전사"

            with loading("호두가 사진 속 글을 옮기고 있어요", provider_desc, "read"), st.status(f"{provider_desc} · 전사 진행", expanded=True) as status_box:
                success_count = 0
                fail_count = 0

                for idx, job in enumerate(ocr_jobs):
                    status_box.write(f"[{idx + 1}/{len(ocr_jobs)}] 페이지에서 문항을 찾는 중…")
                    # Claim the job
                    claimed = job_mgr.claim_next_job()
                    target_job = claimed if claimed else job
                    ok = job_mgr.process_job(target_job, ocr_provider=ocr_provider)
                    if ok:
                        success_count += 1
                        status_box.write(f"[{idx + 1}/{len(ocr_jobs)}] 완료")
                    else:
                        fail_count += 1
                        status_box.write(f"[{idx + 1}/{len(ocr_jobs)}] 실패 또는 건너뜀")

                if fail_count == 0:
                    status_box.update(
                        label=f"전사 완료 (성공 {success_count}건)",
                        state="complete",
                        expanded=False
                    )
                else:
                    status_box.update(
                        label=f"전사 완료 (성공 {success_count}건, 실패·건너뜀 {fail_count}건)",
                        state="error",
                        expanded=True
                    )

            show_state("글을 옮기는 작업을 마쳤어요", f"성공 {success_count}건 · 실패·건너뜀 {fail_count}건. 원본과 대조한 뒤 승인해 주세요.", "done" if fail_count == 0 else "think", "success" if fail_count == 0 else "error")
            st.info("**전사 검수** 탭에서 원본 사진과 옮긴 글을 비교하고 승인하세요.")
