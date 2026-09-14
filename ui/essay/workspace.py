"""
Main Workspace Coordinator for Essay Archive System.
"""

from __future__ import annotations
import json
import streamlit as st
from ui.hodu import page_header, section_intro, loading, show_state
from pathlib import Path

from core.essay.repository import EssayRepository, DEFAULT_ESSAY_ARCHIVE_ROOT
from core.essay.backup import EssayBackupService
from core.essay.seed import SEED_DIR_ENV, seed_data_file
from ui.essay.import_view import render_import_view
from ui.essay.review_view import render_review_view
from ui.essay.library_view import render_essay_library_view
from ui.essay.search_view import render_essay_search_view
from ui.essay.style_view import render_style_view


def get_or_create_essay_repo() -> EssayRepository:
    if "essay_repository" not in st.session_state:
        st.session_state["essay_repository"] = EssayRepository(archive_root=DEFAULT_ESSAY_ARCHIVE_ROOT)
    return st.session_state["essay_repository"]


def render_essay_workspace():
    repo = get_or_create_essay_repo()

    page_header("자기소개서 작업실", "사진 속 글부터 나의 초안까지, 호두와 차근차근 모으고 다듬어요.", "organize", "호두랑 · 나답게 쓰기")

    tab_lib, tab_import, tab_review, tab_search, tab_style, tab_settings = st.tabs([
        "보관함", "자료 추가", "전사 검수", "근거 검색", "문체 편집", "설정·백업"
    ])

    with tab_lib:
        render_essay_library_view(repo)

    with tab_import:
        render_import_view(repo)

    with tab_review:
        render_review_view(repo)

    with tab_search:
        render_essay_search_view(repo)

    with tab_style:
        render_style_view(repo)

    with tab_settings:
        section_intro("설정·백업", "모아 둔 글과 원본을 안전하게 챙겨두세요.", "작업실 관리")

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.markdown("##### 전체 백업")
            st.caption("보관함의 글과 원본 이미지를 ZIP 파일 하나로 저장합니다.")
            if st.button("백업 만들기", use_container_width=True):
                backup_dest = repo.exports_dir / "essay_archive_backup.zip"
                with loading("호두가 자료를 챙기고 있어요", "원본과 글을 한 묶음으로 백업해요.", "organize"):
                    res = EssayBackupService.create_backup(repo, backup_dest)
                show_state("자료를 모두 챙겼어요", f"원본 {res['sources_count']}개 · {res['total_bytes'] / 1024:.1f} KB. 아래에서 백업을 내려받으세요.", "done", "success")
                with open(backup_dest, "rb") as bf:
                    st.download_button(
                        "백업 파일 다운로드",
                        data=bf.read(),
                        file_name="essay_archive_backup.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

        with col_s2:
            st.markdown("##### 샘플 자료 불러오기")
            st.caption("준비된 샘플 자료를 가져옵니다. 이미 있는 자료는 중복으로 추가되지 않습니다.")
            seed_p = seed_data_file("seed.json")
            if st.button("샘플 자료 가져오기", use_container_width=True, disabled=seed_p is None,
                         help=f"{SEED_DIR_ENV} 폴더의 data/seed.json을 사용합니다."):
                with open(seed_p, "r", encoding="utf-8") as f:
                    seed_data = json.load(f)
                imp_res = repo.import_seed_data(seed_data)
                st.success(f"샘플 자료를 가져왔습니다: 새 문서 {imp_res['documents']}건, 답변 {imp_res['answers']}건 등록됨.")
                st.rerun()

        st.divider()
        st.caption(f"저장 위치: `{repo.archive_root}`", help="환경변수 ESSAY_ARCHIVE_ROOT로 바꿀 수 있습니다.")
