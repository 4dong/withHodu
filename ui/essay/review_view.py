"""
Review View: Transcription inspection, original photo comparison, and review approval.
"""

from __future__ import annotations
import streamlit as st
from ui.hodu import page_header, show_state, loading
from PIL import Image, ImageOps

from core.essay.repository import EssayRepository
from core.essay.retrieval import EssaySearchEngine
from core.essay.embedding import get_active_embedding_provider
from core.essay.tagging import TagService
from core.essay.jobs import JobManager
from core.essay.transcription import get_active_ocr_provider


def render_review_view(repo: EssayRepository):
    page_header('전사 검수', '옮긴 글을 원본 사진과 비교해 고친 뒤 승인해요. 승인한 문항만 검색에 쓰여요.')

    # Check for pending OCR jobs in the background queue
    with repo.get_connection() as conn:
        cur = conn.execute("SELECT COUNT(*) as cnt FROM jobs WHERE kind = 'ocr' AND status IN ('queued', 'running')")
        pending_jobs = cur.fetchone()["cnt"]
        cur = conn.execute("SELECT COUNT(*) as cnt FROM jobs WHERE kind = 'ocr' AND status = 'failed'")
        failed_jobs = cur.fetchone()["cnt"]

    if pending_jobs > 0:
        c1, c2 = st.columns([3, 1])
        with c1:
            st.warning(f"대기 중인 전사 작업이 **{pending_jobs}건** 있습니다.")
        with c2:
            if st.button("지금 실행", type="primary", key="run_pending_jobs_btn"):
                job_mgr = JobManager(repo)
                provider = get_active_ocr_provider()
                with loading("사진 속 글을 옮기고 있어요", "", "read"), st.status("전사 진행", expanded=True) as status_box:
                    done = 0
                    while True:
                        job = job_mgr.claim_next_job()
                        if not job:
                            break
                        status_box.write(f"작업 {job.id[:8]} 처리 중…")
                        job_mgr.process_job(job, ocr_provider=provider)
                        done += 1
                    status_box.update(label=f"{done}건 처리 완료", state="complete")
                st.rerun()

    # View mode toggle: unreviewed only vs all documents
    col_vm1, col_vm2 = st.columns([3, 1])
    with col_vm1:
        view_mode = st.radio(
            "보기",
            options=["unreviewed", "all"],
            format_func=lambda x: "검수 대기만" if x == "unreviewed" else "전체",
            horizontal=True,
            key="review_view_mode_radio"
        )

    # Get documents with answers
    docs = repo.list_documents(include_deleted=False)
    doc_meta_list = []
    for d in docs:
        answers = repo.get_answers_for_document(d.id)
        if not answers:
            continue
        unreviewed_cnt = sum(1 for _, rev in answers if rev and rev.review_status == "needs_user_review")
        approved_cnt = sum(1 for _, rev in answers if rev and rev.review_status == "approved")
        doc_meta_list.append({
            "doc": d,
            "answers": answers,
            "unreviewed_cnt": unreviewed_cnt,
            "approved_cnt": approved_cnt,
            "total_cnt": len(answers)
        })

    if view_mode == "unreviewed":
        filtered_meta = [m for m in doc_meta_list if m["unreviewed_cnt"] > 0]
    else:
        filtered_meta = doc_meta_list

    if not filtered_meta:
        if view_mode == "unreviewed":
            show_state("지금 확인할 문항은 없어요", "승인된 문서는 전체를 선택해 확인할 수 있어요.", "rest", "empty")
        else:
            show_state("아직 검수할 글이 없어요", "자료 추가에서 사진이나 문서를 먼저 올려 주세요.", "rest", "empty")
        return

    doc_options = {}
    for m in filtered_meta:
        m_doc = m["doc"]
        c_name = m_doc.company
        t_name = m_doc.title
        unrev = m["unreviewed_cnt"]
        appr = m["approved_cnt"]
        total = m["total_cnt"]
        status_txt = "모두 승인" if unrev == 0 else f"검수 대기 {unrev}건"
        doc_options[m_doc.id] = f"[{c_name}] {t_name} · {status_txt} · 승인 {appr}/{total}"

    selected_doc_id = st.selectbox(
        "지원서",
        key="essay_review_doc",
        options=list(doc_options.keys()),
        format_func=lambda x: doc_options[x]
    )

    selected_meta = next(m for m in filtered_meta if m["doc"].id == selected_doc_id)
    doc = selected_meta["doc"]
    answers = selected_meta["answers"]

    # Filter target answers according to view mode
    if view_mode == "unreviewed" and selected_meta["unreviewed_cnt"] > 0:
        target_answers = [(a, r) for a, r in answers if r and r.review_status == "needs_user_review"]
    else:
        target_answers = [(a, r) for a, r in answers if r]

    if not target_answers:
        st.info("해당 문서에는 표시할 문항이 없습니다.")
        return

    ans_options = {
        a.id: f"문항 {a.question_number}: {'승인 완료 ·' if r.review_status == 'approved' else '검수 대기 ·'} {r.question_text[:28]}..."
        for a, r in target_answers
    }
    selected_ans_id = st.selectbox(
        "문항",
        key="essay_review_answer",
        options=list(ans_options.keys()),
        format_func=lambda x: ans_options[x]
    )

    ans, rev = next((a, r) for a, r in target_answers if a.id == selected_ans_id)
    spans = repo.get_source_spans(rev.id)

    # Status banner for the selected question
    if rev.review_status == "approved":
        st.success("**승인 완료**: 검색에 반영된 문항입니다. 수정한 뒤 다시 승인할 수 있습니다.")
    else:
        st.warning("**검수 대기**: 원본과 비교해 확인한 뒤 승인해 주세요.")

    st.divider()

    # Load all pages and source files for this document
    with repo.get_connection() as conn:
        cur = conn.execute("""
            SELECT dp.page_id, dp.order_index, dp.page_kind, p.physical_page, s.storage_key, s.original_name
            FROM document_pages dp
            JOIN pages p ON dp.page_id = p.id
            JOIN source_files s ON p.source_file_id = s.id
            WHERE dp.document_id = ?
            ORDER BY dp.order_index ASC
        """, (doc.id,))
        all_pages = [dict(r) for r in cur.fetchall()]

    col_left, col_right = st.columns([1.1, 1.2])

    with col_left:
        st.subheader("원본")

        if not all_pages:
            st.info("연결된 원본 이미지 파일이 없습니다.")
        else:
            # Smart default page calculation:
            # If cover exists at index 0, answer question 1 corresponds to index 1 (the first non-cover page)
            non_cover_pages = [p for p in all_pages if p.get("page_kind") != "cover"]
            if non_cover_pages and 1 <= ans.question_number <= len(non_cover_pages):
                target_p = non_cover_pages[ans.question_number - 1]
                default_idx = next((i for i, p in enumerate(all_pages) if p["page_id"] == target_p["page_id"]), 0)
            else:
                default_idx = min(max(0, ans.question_number - 1), len(all_pages) - 1)

            # Session state key for current viewing page of this answer
            page_nav_key = f"active_page_idx_{doc.id}_{ans.id}"
            if page_nav_key not in st.session_state:
                st.session_state[page_nav_key] = default_idx

            current_idx = st.session_state[page_nav_key]
            # Ensure within range
            if current_idx >= len(all_pages):
                current_idx = 0
                st.session_state[page_nav_key] = 0

            # 1. Page Switcher Controls
            nav_col1, nav_col2, nav_col3 = st.columns([1, 3.2, 1])
            with nav_col1:
                if st.button("이전", key=f"prev_p_{ans.id}", disabled=(current_idx <= 0), use_container_width=True):
                    st.session_state[page_nav_key] = max(0, current_idx - 1)
                    st.rerun()
            with nav_col3:
                if st.button("다음", key=f"next_p_{ans.id}", disabled=(current_idx >= len(all_pages) - 1), use_container_width=True):
                    st.session_state[page_nav_key] = min(len(all_pages) - 1, current_idx + 1)
                    st.rerun()
            with nav_col2:
                selected_page_idx = st.selectbox(
                    "대조할 사진 선택",
                    options=list(range(len(all_pages))),
                    index=current_idx,
                    format_func=lambda i: (
                        f"[{i + 1}/{len(all_pages)}] "
                        f"{'표지 · ' if all_pages[i]['page_kind'] == 'cover' else '본문 · '} "
                        f"{all_pages[i]['original_name']}"
                    ),
                    label_visibility="collapsed",
                    key=f"sel_box_{ans.id}"
                )
                if selected_page_idx != current_idx:
                    st.session_state[page_nav_key] = selected_page_idx
                    st.rerun()

            active_page = all_pages[current_idx]

            # 2. Image Manipulation Controls: Rotation & Zoom
            rot_key = f"rot_angle_{active_page['page_id']}"
            if rot_key not in st.session_state:
                st.session_state[rot_key] = 0
            cur_angle = st.session_state[rot_key]

            ctl_col1, ctl_col2, ctl_col3, ctl_col4 = st.columns(4)
            with ctl_col1:
                if st.button("왼쪽 90°", key=f"rot_l_{active_page['page_id']}", use_container_width=True):
                    st.session_state[rot_key] = (cur_angle - 90) % 360
                    st.rerun()
            with ctl_col2:
                if st.button("오른쪽 90°", key=f"rot_r_{active_page['page_id']}", use_container_width=True):
                    st.session_state[rot_key] = (cur_angle + 90) % 360
                    st.rerun()
            with ctl_col3:
                if st.button("180°", key=f"rot_180_{active_page['page_id']}", use_container_width=True):
                    st.session_state[rot_key] = (cur_angle + 180) % 360
                    st.rerun()
            with ctl_col4:
                if st.button("원래대로", key=f"rot_rst_{active_page['page_id']}", use_container_width=True):
                    st.session_state[rot_key] = 0
                    st.rerun()

            zoom_val = st.slider(
                "확대",
                min_value=50,
                max_value=250,
                value=100,
                step=25,
                format="%d%%",
                key=f"zoom_slider_{active_page['page_id']}"
            )

            # 3. Load, Auto-Orient, Rotate, and Render Image
            file_p = repo.get_source_file_path(active_page["storage_key"])
            if file_p and file_p.exists():
                try:
                    raw_img = Image.open(file_p)
                    # Auto-correct orientation from camera EXIF tag
                    oriented_img = ImageOps.exif_transpose(raw_img)
                    # Apply user manual rotation
                    if cur_angle != 0:
                        display_img = oriented_img.rotate(-cur_angle, expand=True)
                    else:
                        display_img = oriented_img

                    # Display image with zoom support
                    if zoom_val == 100:
                        st.image(
                            display_img,
                            caption=f"원본 사진 [{current_idx + 1}/{len(all_pages)}]: {active_page['original_name']} (회전: {cur_angle}°)",
                            use_container_width=True
                        )
                    else:
                        # Scaled display in scrollable container
                        base_w, _ = display_img.size
                        scaled_w = max(300, int(base_w * (zoom_val / 100)))
                        st.image(
                            display_img,
                            caption=f"원본 사진 [{current_idx + 1}/{len(all_pages)}]: {active_page['original_name']} (회전: {cur_angle}°, 확대: {zoom_val}%)",
                            width=scaled_w
                        )
                except Exception as e:
                    st.error(f"이미지 로드 중 오류: {e}")
            else:
                st.warning("디스크에서 원본 사진 파일을 찾을 수 없습니다.")

        # Uncertain spans
        if spans:
            st.markdown("##### 확인이 필요한 부분")
            for s in spans:
                if s.uncertain:
                    st.warning(f"위치 [{s.start_char}:{s.end_char}]: {s.note or '[판독불가]'}")

    with col_right:
        st.subheader("옮긴 글 편집")

        q_text = st.text_area(
            "질문",
            value=rev.question_text,
            height=85,
            key=f"q_{rev.id}"
        )
        b_text = st.text_area(
            "본문",
            value=rev.body_text,
            height=420,
            key=f"b_{rev.id}",
            help="원본 사진을 대조하며 가려진 글자나 오탈자를 직접 수정합니다."
        )

        b_no_spaces = len("".join(b_text.split()))
        st.caption(f"{len(b_text)}자 (공백 제외 {b_no_spaces}자)")


        # Evidence-backed tag suggestions
        tag_svc = TagService(repo)
        detected_tags = tag_svc.extract_deterministic_tags(b_text)
        if detected_tags:
            st.markdown("##### 추천 태그")
            tag_cols = st.columns(min(len(detected_tags), 4))
            for idx, (t, ev) in enumerate(detected_tags[:4]):
                with tag_cols[idx]:
                    st.badge(f"{t.facet}: {t.label}")
                    st.caption(f"근거: '{ev}'")

        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            if st.button("승인하기", type="primary", use_container_width=True):
                # Save changes if any
                if q_text != rev.question_text or b_text != rev.body_text:
                    new_rev = repo.add_revision(
                        answer_id=ans.id,
                        parent_revision_id=rev.id,
                        question_text=q_text,
                        body_text=b_text,
                        origin="manual",
                        review_status="approved",
                        set_as_current=True
                    )
                    rev_id_to_index = new_rev.id
                else:
                    repo.set_revision_status(rev.id, "approved")
                    rev_id_to_index = rev.id

                # Index revision with unified active embedding provider
                search_engine = EssaySearchEngine(repo, embedding_provider=get_active_embedding_provider())
                search_engine.index_revision(rev_id_to_index)

                # Check if all answers in the document are now approved
                all_ans = repo.get_answers_for_document(doc.id)
                if all_ans and all(r and r.review_status == "approved" for _, r in all_ans):
                    doc.grouping_status = "confirmed"
                    doc.completeness = "complete"
                    repo.update_document(doc)

                # Real-time sync to document folder (.txt, .md, images)
                try:
                    repo.sync_document_folder(doc.id)
                except Exception:
                    pass

                st.success("승인했어요. 검색과 문서 폴더에 반영했어요.")
                st.rerun()

        with col_b2:
            if st.button("임시 저장", use_container_width=True):
                repo.add_revision(
                    answer_id=ans.id,
                    parent_revision_id=rev.id,
                    question_text=q_text,
                    body_text=b_text,
                    origin="manual",
                    review_status="needs_user_review",
                    set_as_current=True
                )
                try:
                    repo.sync_document_folder(doc.id)
                except Exception:
                    pass
                st.success("수정 사항이 새 리비전으로 저장되었습니다.")
                st.rerun()

        with col_b3:
            if st.button("보류", use_container_width=True):
                st.info("검수를 보류했습니다.")
