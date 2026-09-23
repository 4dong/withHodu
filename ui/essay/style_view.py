"""
Style View: Draft rewriting, style profile transfer, fact preservation validation, and version adoption.
"""

from __future__ import annotations
import json
import streamlit as st
from ui.hodu import page_header, loading

from core.essay.repository import EssayRepository
from core.essay.style import (
    EssayStyleService, STYLE_PRESETS,
    RevisionConflictError
)


def render_style_view(repo: EssayRepository):
    page_header('문체 편집', '초안을 원하는 문체로 다듬고, 수치와 사실이 그대로인지 확인한 뒤 새 버전으로 저장해요.')

    style_svc = EssayStyleService(repo)

    col_draft, col_config = st.columns([1.2, 0.8])

    with col_draft:
        st.subheader("내 초안")

        # Option to load from own_draft documents
        own_docs = repo.list_documents(collection="own_draft", include_deleted=False)
        load_options = {"direct": "직접 붙여넣기"}
        own_ans_map = {}
        for d in own_docs:
            answers = repo.get_answers_for_document(d.id)
            for a, r in answers:
                if r:
                    key = f"{d.id}:{a.id}"
                    load_options[key] = f"[{d.company}] {d.title} - 문항 {a.question_number}"
                    own_ans_map[key] = r

        draft_sel = st.selectbox(
            "보관함에서 초안 불러오기",
            options=list(load_options.keys()),
            format_func=lambda x: load_options[x]
        )

        initial_text = ""
        cur_rev_id = None
        if draft_sel != "direct" and draft_sel in own_ans_map:
            initial_text = own_ans_map[draft_sel].body_text
            cur_rev_id = own_ans_map[draft_sel].id

        draft_input = st.text_area(
            "초안 텍스트",
            value=initial_text,
            height=280,
            placeholder="다듬을 초안을 붙여넣거나 위에서 불러오세요.",
            key="style_user_draft_text"
        )
        draft_no_spaces = len("".join(draft_input.split()))
        st.caption(f"현재 글자 수: {len(draft_input)}자 (공백 제외 {draft_no_spaces}자)")

    with col_config:
        st.subheader("편집 설정")
        chosen_style = st.selectbox("스타일 프리셋", options=list(STYLE_PRESETS.keys()))
        st.caption(STYLE_PRESETS[chosen_style]["description"])

        mode_choice = st.radio(
            "사실 보존 모드",
            options=["strict_preserve", "condense"],
            format_func=lambda x: "사실 그대로 유지 (수치·내용 보존)" if x == "strict_preserve" else "분량 줄이기 (일부 생략 허용)"
        )

        use_limit = st.checkbox("글자 수 제한 적용")
        max_chars = None
        if use_limit:
            max_chars = st.number_input("최대 글자 수 (공백 포함)", min_value=10, max_value=2000, value=700, step=50)

        # Reference selection for style transfer
        ref_docs = repo.list_documents(collection="reference", include_deleted=False)
        ref_options = {"none": "참고 자소서 없음 (프리셋 규칙만 적용)"}
        ref_ans_map = {}
        for d in ref_docs:
            answers = repo.get_answers_for_document(d.id)
            for a, r in answers:
                if r:
                    k = f"{d.id}:{a.id}"
                    ref_options[k] = f"[{d.company} {d.role}] {r.question_text[:25]}..."
                    ref_ans_map[k] = r.id

        ref_sel = st.selectbox(
            "참고 자소서 (선택)",
            options=list(ref_options.keys()),
            format_func=lambda x: ref_options[x]
        )
        target_ref_rev_id = ref_ans_map.get(ref_sel)

        run_rewrite = st.button("수정안 만들기", type="primary", use_container_width=True)

    # Execute rewriting
    if run_rewrite:
        if not draft_input.strip():
            st.error("초안 텍스트를 입력해 주세요.")
            return

        with loading("수정안을 만들고 있어요", "", "read"):
            # F11: Save user edits in text_area as a new revision before generating proposal
            if cur_rev_id:
                old_rev = repo.get_revision(cur_rev_id)
                if old_rev and old_rev.body_text.strip() != draft_input.strip():
                    ans = repo.get_answer(old_rev.answer_id)
                    new_edit_rev = repo.add_revision(
                        answer_id=ans.id,
                        parent_revision_id=cur_rev_id,
                        question_text=old_rev.question_text,
                        body_text=draft_input.strip(),
                        origin="manual",
                        review_status="approved",
                        set_as_current=True
                    )
                    cur_rev_id = new_edit_rev.id
            else:
                # If draft was typed directly, create a draft document and answer to track
                docs = repo.list_documents(collection="own_draft")
                draft_doc = docs[0] if docs else repo.create_document(
                    type("Doc", (), {
                        "id": "user_workspace_drafts", "title": "내 작업실 초안",
                        "company": "미지정", "division": "미지정", "role": "미지정",
                        "collection": "own_draft", "author": "나",
                        "recruitment_year": 2026, "outcome": "unknown",
                        "grouping_status": "confirmed", "completeness": "complete",
                        "notes": None, "deleted_at": None, "created_at": "now", "updated_at": "now"
                    })()
                )
                _, rev_temp = repo.create_answer(
                    document_id=draft_doc.id,
                    question_number=len(repo.get_answers_for_document(draft_doc.id)) + 1,
                    question_text="자유 초안",
                    body_text=draft_input.strip(),
                    origin="manual"
                )
                cur_rev_id = rev_temp.id

            proposal = style_svc.generate_rewrite_proposal(
                input_revision_id=cur_rev_id,
                style_name=chosen_style,
                mode=mode_choice,
                max_chars=max_chars,
                reference_revision_id=target_ref_rev_id
            )
            st.session_state["latest_rewrite_proposal"] = proposal
            st.session_state["expected_input_rev_id"] = cur_rev_id

    # Display Rewrite Proposal Results
    if "latest_rewrite_proposal" in st.session_state:
        proposal = st.session_state["latest_rewrite_proposal"]
        exp_rev_id = st.session_state.get("expected_input_rev_id")
        val = json.loads(proposal.validation_json)

        st.divider()
        st.subheader("수정 결과")

        col_out1, col_out2 = st.columns(2)
        with col_out1:
            st.markdown("##### 원본")
            in_rev = repo.get_revision(proposal.input_revision_id)
            with st.container(border=True, key="card_style_input"):
                st.write(in_rev.body_text if in_rev else "(원본 조회 불가)")

        with col_out2:
            st.markdown("##### 수정안")
            with st.container(border=True, key="card_style_output"):
                st.write(proposal.output_text)

        # Validation & Safety Summary
        with st.container(border=True, key="card_style_check"):
            st.markdown("#### 사실 보존 확인")
            col_v1, col_v2, col_v3 = st.columns(3)
            with col_v1:
                st.metric("수정본 총 글자 수", f"{val['char_count_total']}자", f"공백제외 {val['char_count_no_spaces']}자")
            with col_v2:
                status_text = "모두 보존" if val["can_accept"] else "확인 필요"
                st.metric("수치 및 핵심 사실", status_text)
            with col_v3:
                len_status = "충족" if val["length_satisfied"] else "초과"
                st.metric("글자 수 제약", len_status)

            if val["preserved_facts"]:
                st.caption(f"• 보존된 수치/명제: {', '.join(val['preserved_facts'])}")
            if val["missing_facts"]:
                st.warning(f"• 누락된 원본 사실: {', '.join(val['missing_facts'])}")
            if val["forbidden_added_facts"]:
                st.error(f"• 참고 자료의 경험·수치가 섞였습니다 (채택 불가): {', '.join(val['forbidden_added_facts'])}")
            if val.get("length_warning"):
                st.warning(f"• 길이 경고: {val['length_warning']}")

        # Adoption Action
        col_act1, col_act2 = st.columns([2, 1])
        with col_act1:
            st.caption("채택하면 원본은 그대로 두고 새 버전으로 저장합니다.")
        with col_act2:
            adopt_disabled = not val["can_accept"] or proposal.status == "accepted"
            btn_label = "채택됨" if proposal.status == "accepted" else "새 버전으로 채택"
            if st.button(btn_label, type="primary", disabled=adopt_disabled, use_container_width=True):
                try:
                    new_v = style_svc.accept_proposal(proposal, expected_input_revision_id=exp_rev_id)
                    st.success(f"새 버전으로 저장했습니다. (버전 {new_v.id[:8]})")
                    st.session_state["latest_rewrite_proposal"].status = "accepted"
                    st.rerun()
                except RevisionConflictError as e:
                    st.error(f"채택하지 못했습니다. 그사이 원본이 바뀌었습니다: {e}")
