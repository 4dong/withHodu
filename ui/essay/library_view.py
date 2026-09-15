"""
Library View: essays shelved like books. Each shelf holds one collection and scrolls sideways, with
bookends grouping the spines by company; the open essay always sits in its own card below, with
export and delete tucked into one menu.
"""

from __future__ import annotations
import hashlib
import html
import random
import re
from typing import Dict, List, Tuple

import streamlit as st
from ui.hodu import page_header, show_state

from core.essay.models import Document
from core.essay.repository import EssayRepository

OPEN_DOC_KEY = "essay_shelf_open_doc_id"
SPINE_TONES = 6

COLLECTION_SHELVES = [
    ("own_draft", "내 초안"),
    ("own_experience", "내 경험"),
    ("reference", "참고 자소서"),
    ("recruitment_notice", "채용 공고"),
]
COLLECTION_LABELS = dict(COLLECTION_SHELVES)
ORIGIN_LABELS = {"ocr": "사진 전사", "manual": "직접 작성", "seed": "샘플 자료"}


def group_shelves(docs: List[Document]) -> List[Tuple[str, List[Tuple[str, List[Document]]]]]:
    """Collections in shelf order (unknown ones last), companies sorted within a shelf, titles sorted within a company."""
    known = [c for c, _ in COLLECTION_SHELVES]
    collections = sorted({d.collection for d in docs}, key=lambda c: (known.index(c) if c in known else len(known), c))
    shelves = []
    for collection in collections:
        companies: Dict[str, List[Document]] = {}
        for d in docs:
            if d.collection == collection:
                companies.setdefault(d.company or "기타", []).append(d)
        shelves.append((collection, [(name, sorted(group, key=lambda d: d.title)) for name, group in sorted(companies.items())]))
    return shelves


def spine_label(doc: Document) -> str:
    """The bookend already names the company, so the spine drops a leading company name from the title."""
    title = (doc.title or "").strip()
    company = (doc.company or "").strip()
    rest = title[len(company):].strip(" _-·") if company and title.startswith(company) else ""
    return rest or title or "제목 없음"


def spine_key(doc: Document, approved: bool) -> str:
    # The key carries the company tone, review state and book size so CSS can style each spine without
    # per-book styles. Sizes vary like real books on a shelf but stay the same for a given document.
    tone = int(hashlib.md5((doc.company or "").encode("utf-8")).hexdigest(), 16) % SPINE_TONES
    size = int(hashlib.md5(doc.id.encode("utf-8")).hexdigest(), 16)
    return f"essay_spine_t{tone}_{'ok' if approved else 'wait'}_h{size % 4}_w{size // 4 % 3}_{doc.id}"


def _is_approved(answers) -> bool:
    return bool(answers) and all(r and r.review_status == "approved" for _, r in answers)


def _open_document(doc_id: str):
    st.session_state[OPEN_DOC_KEY] = doc_id


def render_essay_library_view(repo: EssayRepository):
    page_header('보관함', '선반은 자료 구분별로, 선반 안은 기업별로 꽂혀 있어요.')

    docs = repo.list_documents(include_deleted=False)
    if not docs:
        show_state("아직 책장이 비어 있어요", "자료 추가에서 자소서를 등록해 주세요.", "organize", "empty")
        return

    answers_by_doc = {d.id: repo.get_answers_for_document(d.id) for d in docs}
    approved = {d.id: _is_approved(answers_by_doc[d.id]) for d in docs}

    open_id = st.session_state.get(OPEN_DOC_KEY)
    if open_id not in answers_by_doc:
        # Nothing picked yet, or the open essay was deleted: pick one at random once and keep it across reruns.
        open_id = random.choice(docs).id
        st.session_state[OPEN_DOC_KEY] = open_id

    pending = sum(1 for d in docs if not approved[d.id])
    summary = f"책 {len(docs)}권 · 승인 완료 {len(docs) - pending}권 · 검수 대기 {pending}권"
    st.caption(summary + (" · 책등의 주황 점은 검수 대기" if pending else ""))

    _render_bookshelf(docs, approved, open_id)
    open_doc = next(d for d in docs if d.id == open_id)
    _render_open_book(repo, open_doc, answers_by_doc[open_id])


def _render_bookshelf(docs: List[Document], approved: Dict[str, bool], open_id: str):
    with st.container(key="essay_bookshelf"):
        for s_idx, (collection, companies) in enumerate(group_shelves(docs)):
            label = COLLECTION_LABELS.get(collection, collection)
            with st.container(key=f"essay_shelf_row_{s_idx}", horizontal=True, wrap=False, vertical_alignment="bottom"):
                st.markdown(f'<div class="essay-shelf-label">{html.escape(label)}</div>', unsafe_allow_html=True, width="content")
                with st.container(key=f"essay_shelf_rail_{s_idx}", horizontal=True, wrap=False, vertical_alignment="bottom"):
                    for company, company_docs in companies:
                        st.markdown(f'<div class="essay-bookend">{html.escape(company)}</div>', unsafe_allow_html=True, width="content")
                        for d in company_docs:
                            st.button(
                                spine_label(d),
                                key=spine_key(d, approved[d.id]),
                                help=" · ".join(v for v in [d.title, d.division, d.role, "승인 완료" if approved[d.id] else "검수 대기"] if v),
                                type="primary" if d.id == open_id else "secondary",
                                on_click=_open_document,
                                args=(d.id,),
                                width="content",
                            )


def _html_lines(text: str, reflow: bool = False) -> str:
    text = text.replace("\r\n", "\n").strip()
    if reflow:
        # Photo transcriptions break at every printed line; rejoin the lines within each paragraph.
        text = "\n".join(" ".join(paragraph.split("\n")) for paragraph in re.split(r"\n\s*\n", text))
    # One HTML line keeps blank lines in the text from ending the block and turning the rest into markdown.
    return html.escape(text).replace("\n", "<br>")


def _render_open_book(repo: EssayRepository, doc: Document, answers):
    appr_cnt = sum(1 for _, r in answers if r and r.review_status == "approved")
    eyebrow = " · ".join(v for v in [COLLECTION_LABELS.get(doc.collection, doc.collection), doc.company] if v)
    # Division and role are often the same text; show it once.
    meta = " · ".join(dict.fromkeys(v for v in [doc.division, doc.role, f"승인 {appr_cnt}/{len(answers)}"] if v))
    notes = f'<p class="essay-book-notes">{_html_lines(doc.notes, reflow=True)}</p>' if doc.notes and doc.notes.strip() else ''

    with st.container(key="essay_open_book"):
        with st.container(key="essay_open_book_head", horizontal=True, wrap=False, vertical_alignment="top"):
            st.markdown(
                f'<div class="essay-book-head"><p class="essay-book-eyebrow">{html.escape(eyebrow)}</p>'
                f'<h3 class="essay-book-title">{html.escape(doc.title)}</h3>'
                f'<p class="essay-book-meta">{html.escape(meta)}</p>{notes}</div>',
                unsafe_allow_html=True,
                width="stretch"
            )
            _render_book_actions(repo, doc)

        if not answers:
            st.caption("옮겨 적은 문항이 없어요. 전사 검수에서 확인해 주세요.")

        for ans, rev in answers:
            if rev:
                question = html.escape(rev.question_text)
                body = _html_lines(rev.body_text)
                status = "승인 완료" if rev.review_status == "approved" else "검수 대기"
                no_spaces = len("".join(rev.body_text.split()))
                foot = f"{status} · {ORIGIN_LABELS.get(rev.origin, rev.origin)} · {len(rev.body_text)}자 (공백 제외 {no_spaces}자)"
            else:
                question, body, foot = "(질문 미등록)", "아직 옮겨 적지 않았어요.", ""
            st.markdown(
                f'<section class="essay-answer"><p class="essay-answer-q"><span class="essay-answer-no">문항 {ans.question_number}</span>{question}</p>'
                f'<div class="essay-answer-body">{body}</div>'
                + (f'<p class="essay-answer-foot">{html.escape(foot)}</p>' if foot else '') + '</section>',
                unsafe_allow_html=True
            )


def _render_book_actions(repo: EssayRepository, doc: Document):
    doc_id = doc.id
    base_name = f"{doc.company}_{doc.role}_{doc_id[:6]}"
    with st.popover("", icon=":material/more_horiz:", help="내보내기·삭제", width="content", key="essay_open_book_actions"):
        st.markdown("**내보내기**")
        # Files are generated only when a button is pressed, not on every rerun.
        st.download_button("Markdown", data=lambda: repo.export_document_markdown(doc_id), file_name=f"{base_name}.md",
                           mime="text/markdown", width="stretch", key=f"dl_md_{doc_id}")
        st.download_button("텍스트", data=lambda: repo.export_document_txt(doc_id), file_name=f"{base_name}.txt",
                           mime="text/plain", width="stretch", key=f"dl_txt_{doc_id}")
        st.download_button("ZIP", data=lambda: repo.export_document_zip(doc_id).read_bytes(),
                           file_name=f"export_{doc.company}_{doc_id[:6]}.zip", mime="application/zip",
                           width="stretch", key=f"dl_zip_{doc_id}")
        st.divider()
        confirm_del = st.checkbox("이 자소서를 삭제합니다", key=f"del_confirm_{doc_id}")
        if st.button("문서 삭제", icon=":material/delete:", key=f"del_{doc_id}", disabled=not confirm_del, width="stretch"):
            repo.delete_document(doc_id)
            st.session_state.pop(OPEN_DOC_KEY, None)
            st.toast("문서를 보관함과 검색 대상에서 제외했습니다.")
            st.rerun()
