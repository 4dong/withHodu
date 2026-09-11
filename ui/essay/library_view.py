"""
Library View: Document cards, answer exploration, export (MD/TXT/ZIP), and soft deletion.
"""

from __future__ import annotations
import streamlit as st
import html
from typing import Optional

from core.essay.repository import EssayRepository


def render_essay_library_view(repo: EssayRepository):
    st.markdown("### 보관함")
    st.caption("모아 둔 자기소개서를 기업·직무·자료 구분별로 찾아봅니다.")

    # Filter Bar
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        col_choice = st.selectbox(
            "자료 구분",
            key="essay_lib_collection",
            options=["전체", "reference", "own_draft", "own_experience", "recruitment_notice"],
            format_func=lambda x: {
                "전체": "전체 보기",
                "reference": "참고 자소서",
                "own_draft": "내 자소서 초안",
                "own_experience": "내 경험 정리",
                "recruitment_notice": "채용 공고"
            }.get(x, x)
        )
    with col_f2:
        all_docs = repo.list_documents(include_deleted=False)
        companies = sorted(list({d.company for d in all_docs if d.company}))
        comp_choice = st.selectbox("기업", options=["전체"] + companies, key="essay_lib_company")

    with col_f3:
        roles = sorted(list({d.role for d in all_docs if d.role}))
        role_choice = st.selectbox("직무", options=["전체"] + roles, key="essay_lib_role")

    filtered_docs = repo.list_documents(
        collection=None if col_choice == "전체" else col_choice,
        company=None if comp_choice == "전체" else comp_choice,
        role=None if role_choice == "전체" else role_choice,
        include_deleted=False
    )

    if not filtered_docs:
        st.info("조건에 맞는 문서가 없습니다. 필터를 바꾸거나 자료 추가 탭에서 문서를 등록하세요.")
        return

    # Calculate overall approval statistics
    approved_docs_cnt = 0
    for d in filtered_docs:
        ans_list = repo.get_answers_for_document(d.id)
        if ans_list and all(r and r.review_status == "approved" for _, r in ans_list):
            approved_docs_cnt += 1
    pending_docs_cnt = len(filtered_docs) - approved_docs_cnt

    st.markdown(
        f"**전체 {len(filtered_docs)}건** &nbsp;·&nbsp; "
        f"<span style='color:#167347; font-weight:600;'>승인 완료 {approved_docs_cnt}건</span> &nbsp;·&nbsp; "
        f"<span style='color:#925A10; font-weight:600;'>검수 대기 {pending_docs_cnt}건</span>",
        unsafe_allow_html=True
    )

    for doc in filtered_docs:
        answers = repo.get_answers_for_document(doc.id)
        appr_cnt = sum(1 for _, r in answers if r and r.review_status == "approved")
        unrev_cnt = sum(1 for _, r in answers if r and r.review_status == "needs_user_review")

        with st.container(border=True):
            col_t1, col_t2 = st.columns([2.8, 1.2])
            with col_t1:
                col_badge = {
                    "reference": "참고 자소서",
                    "own_draft": "내 초안",
                    "own_experience": "내 경험",
                    "recruitment_notice": "채용 공고"
                }.get(doc.collection, doc.collection)
                st.markdown(f'<div class="ap-document-title">{html.escape(doc.title)}</div><span class="ap-badge">{html.escape(col_badge)}</span>', unsafe_allow_html=True)
                group_label = "묶음 확정" if doc.grouping_status == "confirmed" else "묶음 확인 필요"
                st.caption(" · ".join(v for v in [doc.company, doc.division, doc.role, group_label] if v))

            with col_t2:
                # Clear Korean approval and completeness badge
                if len(answers) > 0 and unrev_cnt == 0:
                    st.success(f"승인 완료 {appr_cnt}/{len(answers)}")
                elif appr_cnt > 0:
                    st.warning(f"일부 승인 {appr_cnt}/{len(answers)}")
                else:
                    st.info(f"검수 대기 {len(answers)}개")

            if doc.notes:
                st.caption(f"메모: {doc.notes}")

            # Answers expander
            with st.expander(f"문항 보기 ({len(answers)}개)"):
                for ans, rev in answers:
                    status_icon = "· 승인 완료" if rev and rev.review_status == "approved" else "· 검수 대기"
                    st.markdown(f"**문항 {ans.question_number}** {status_icon}  \n{rev.question_text if rev else '(아직 전사되지 않음)'}")
                    if rev:
                        st.markdown(rev.body_text)
                        status_label = "승인 완료" if rev.review_status == "approved" else "검수 대기"
                        origin_label = {"ocr": "사진 전사", "manual": "직접 작성", "seed": "샘플 자료"}.get(rev.origin, rev.origin)
                        st.caption(f"{status_label} · {origin_label} · {len(rev.body_text)}자")
                    st.divider()

            # Actions: Export & Delete
            with st.expander("더보기: 내보내기·삭제"):
                col_a1, col_a2, col_a3, col_a4 = st.columns([1, 1, 1, 1])
                with col_a1:
                    md_text = repo.export_document_markdown(doc.id)
                    st.download_button(
                        "Markdown",
                        data=md_text,
                        file_name=f"{doc.company}_{doc.role}_{doc.id[:6]}.md",
                        mime="text/markdown",
                        use_container_width=True,
                        key=f"dl_md_{doc.id}"
                    )
                with col_a2:
                    txt_text = repo.export_document_txt(doc.id)
                    st.download_button(
                        "텍스트",
                        data=txt_text,
                        file_name=f"{doc.company}_{doc.role}_{doc.id[:6]}.txt",
                        mime="text/plain",
                        use_container_width=True,
                        key=f"dl_txt_{doc.id}"
                    )
                with col_a3:
                    zip_path = repo.export_document_zip(doc.id)
                    with open(zip_path, "rb") as zf:
                        st.download_button(
                            "ZIP",
                            data=zf.read(),
                            file_name=f"export_{doc.company}_{doc.id[:6]}.zip",
                            mime="application/zip",
                            use_container_width=True,
                            key=f"dl_zip_{doc.id}"
                        )
                with col_a4:
                    confirm_del = st.checkbox("삭제 확인", key=f"del_confirm_{doc.id}")
                    if st.button("문서 삭제", key=f"del_{doc.id}", use_container_width=True, disabled=not confirm_del):
                        repo.delete_document(doc.id)
                        st.warning("문서를 보관함과 검색 대상에서 제외했습니다.")
                        st.rerun()
