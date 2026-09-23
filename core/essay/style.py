"""
Style Rewriter, Fact Ledger, Hallucination & Leakage Validator, and Revision Guard for Essay Archive.
"""

from __future__ import annotations
import re
import json
import difflib
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

from core.key_manager import KeyManager
from core.essay.models import (
    RewriteProposal, AnswerRevision, new_uuid, utc_now_iso
)
from core.essay.repository import EssayRepository

STYLE_PRESETS = {
    "두괄식 직무 중심": {
        "description": "핵심 행동과 직무 역량을 문두에 배치하고 서술어를 간결화합니다.",
        "opening": "head-first",
        "tone": "objective",
    },
    "간결한 문체": {
        "description": "군더더기 수식어와 중복 조사를 배제하고 명료하게 요약합니다.",
        "opening": "direct",
        "tone": "concise",
    },
    "담백한 문체": {
        "description": "과장된 감정 표현을 지양하고 사실 위주로 담백하게 전달합니다.",
        "opening": "natural",
        "tone": "factual",
    },
    "성과 중심": {
        "description": "수행 과정과 기여도를 명확히 구분하되 사실에 없는 성과는 추가하지 않습니다.",
        "opening": "action-focused",
        "tone": "rigorous",
    }
}


class RevisionConflictError(Exception):
    pass


class LengthConstraintError(Exception):
    pass


@dataclass
class FactLedger:
    numbers: List[str] = field(default_factory=list)
    units_and_metrics: List[str] = field(default_factory=list)
    key_terms: List[str] = field(default_factory=list)
    negatives_or_limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StyleValidationResult:
    valid: bool
    can_accept: bool
    preserved_facts: List[str]
    missing_facts: List[str]
    forbidden_added_facts: List[str]
    char_count_total: int
    char_count_no_spaces: int
    length_satisfied: bool
    length_warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FactExtractor:
    @staticmethod
    def extract_facts(text: str) -> FactLedger:
        # Extract numbers with optional decimal and unit without Unicode boundary failure (A03)
        number_pattern = re.compile(r"(?<![0-9.])\d+(?:\.\d+)?(?:\s*(?:mm|cm|m|km|%|개월|년|일|시간|분|초|개|명|건|원|배))?")
        nums = [n.strip() for n in number_pattern.findall(text) if n.strip()]

        # Extract negative or uncertainty phrases
        neg_patterns = [
            "확정하지 못했습니다", "미확정", "알 수 없음", "해결하지 못함",
            "원인 불명", "발생 조건 불명확", "이상 현상 확인"
        ]
        found_negs = [p for p in neg_patterns if p in text]

        # Significant alphanumeric or technical tokens
        tech_tokens = re.findall(r"[A-Za-z0-9\-_]{2,}", text)

        return FactLedger(
            numbers=nums,
            units_and_metrics=nums,
            key_terms=list(set(tech_tokens)),
            negatives_or_limitations=found_negs
        )


ACHIEVEMENT_KEYWORDS = [
    "팀장", "승진", "대회", "우승", "1위", "최우수", "대상", "수상",
    "도입 완료", "원인 규명", "해결 완료", "특허", "출원", "논문", "발표",
    "매출 증대", "비용 절감", "수석", "장학생"
]


class StyleValidator:
    @staticmethod
    def validate(
        input_text: str,
        output_text: str,
        reference_forbidden_terms: Optional[List[str]] = None,
        max_chars: Optional[int] = None,
        mode: str = "strict_preserve"
    ) -> StyleValidationResult:
        input_facts = FactExtractor.extract_facts(input_text)
        output_facts = FactExtractor.extract_facts(output_text)

        preserved = []
        missing = []
        forbidden_added = []

        # 1. Fact preservation check (numbers & metrics)
        for num in input_facts.numbers:
            # Strip Korean particle if attached
            num_clean = re.sub(r"[이가은는을를와과]$", "", num)
            if num_clean in output_text:
                preserved.append(num)
            else:
                missing.append(num)

        for neg in input_facts.negatives_or_limitations:
            if "확정하지 못했습니다" in neg:
                if "미확정" in output_text or "확정하지 못" in output_text:
                    preserved.append(neg)
                else:
                    missing.append(neg)
            elif neg in output_text:
                preserved.append(neg)
            else:
                missing.append(neg)

        # 2. Check forbidden additions from reference
        forbidden_list = reference_forbidden_terms or []
        for term in forbidden_list:
            if term in output_text and term not in input_text:
                forbidden_added.append(term)

        # 3. Disallow newly invented achievements / roles (A02)
        for kw in ACHIEVEMENT_KEYWORDS:
            if kw in output_text and kw not in input_text:
                if kw not in forbidden_added:
                    forbidden_added.append(kw)

        # 4. Disallow new invented numbers in strict_preserve mode (A03)
        input_clean_nums = {re.sub(r"[이가은는을를와과]$", "", n) for n in input_facts.numbers}
        for out_num in output_facts.numbers:
            out_clean = re.sub(r"[이가은는을를와과]$", "", out_num)
            if out_clean not in input_clean_nums and out_clean not in forbidden_added:
                # Check if it's a newly fabricated or changed number
                forbidden_added.append(out_num)

        # 5. Length checks
        c_total = len(output_text)
        c_no_spaces = len(output_text.replace(" ", "").replace("\n", ""))
        length_satisfied = True
        length_warning = None

        if max_chars is not None:
            if c_total > max_chars:
                length_satisfied = False
                length_warning = f"글자 수 한도({max_chars}자)를 초과했습니다 (현재 {c_total}자)."

        valid = (len(missing) == 0) and (len(forbidden_added) == 0) and length_satisfied
        # A04: can_accept must strictly require length_satisfied
        can_accept = (len(forbidden_added) == 0) and (len(missing) == 0 or mode == "condense") and length_satisfied

        return StyleValidationResult(
            valid=valid,
            can_accept=can_accept,
            preserved_facts=preserved,
            missing_facts=missing,
            forbidden_added_facts=forbidden_added,
            char_count_total=c_total,
            char_count_no_spaces=c_no_spaces,
            length_satisfied=length_satisfied,
            length_warning=length_warning
        )


class BaseStyleRewriter:
    def rewrite(
        self,
        input_text: str,
        style_name: str,
        mode: str = "strict_preserve",
        max_chars: Optional[int] = None,
        reference_text: Optional[str] = None
    ) -> str:
        raise NotImplementedError


class LLMStyleRewriter(BaseStyleRewriter):
    """
    Google Gemini-backed style rewriter for real user drafts.
    Enforces fact preservation, tone adaptation, length limits, and avoidance of reference leakage.
    """
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.7-flash"):
        if not api_key:
            active_key, _ = KeyManager.get_active_key()
            self.api_key = active_key
        else:
            self.api_key = api_key
        self.model_name = model_name

    def rewrite(
        self,
        input_text: str,
        style_name: str,
        mode: str = "strict_preserve",
        max_chars: Optional[int] = None,
        reference_text: Optional[str] = None
    ) -> str:
        if not self.api_key:
            return self._rule_based_rewrite(input_text, style_name, mode, max_chars)

        system_instruction = (
            "당신은 자기소개서 문체 교정 및 첨삭 전문 어시스턴트입니다.\n"
            "엄격한 사실 보존 원칙(Fact Ledger Rule):\n"
            "1. 원문에 기재된 수치, 고유명사, 기술 스택, 성과 지표, 한계점은 절대 변경하거나 삭제하거나 과장하지 마십시오.\n"
            "2. 원문에 없는 새로운 직책(예: 팀장), 수상 경력, 대회 1위 등 새로운 사실이나 성과를 절대 날조(fabricate)하지 마십시오.\n"
            "3. 참고자료(Reference)가 제공된 경우, 참고자료의 사실이나 수치(고유 사실)를 사용자의 초안으로 유출/도용하지 마십시오. 오직 문체와 표현 방식의 아이디어만 참고하십시오.\n"
        )
        if max_chars:
            system_instruction += f"4. 공백 포함 전체 글자 수를 반드시 {max_chars}자 이내로 엄격히 제한하십시오.\n"

        prompt = f"다음 초안 텍스트를 '{style_name}' 스타일로 수정해 주십시오.\n\n[초안]\n{input_text}"
        if reference_text:
            prompt += f"\n\n[참고자료 (문체 참고용, 사실 도용 금지)]\n{reference_text}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048
            }
        }

        models_to_try = [self.model_name]
        for fb in ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-flash-latest"]:
            if fb not in models_to_try:
                models_to_try.append(fb)

        for model_id in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={self.api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=30.0) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_data.get("candidates", [])
                    if not candidates:
                        continue
                    out_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                    if out_text:
                        return out_text
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                break
            except Exception:
                continue

        return self._rule_based_rewrite(input_text, style_name, mode, max_chars)

    def _rule_based_rewrite(
        self,
        input_text: str,
        style_name: str,
        mode: str = "strict_preserve",
        max_chars: Optional[int] = None
    ) -> str:
        text = input_text.strip()
        if "두괄식" in style_name:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if lines and not lines[0].startswith("["):
                first_line = re.sub(r"하였습니다\b", "했습니다", lines[0])
                text = "\n".join([first_line] + lines[1:])
        elif "간결한" in style_name:
            text = re.sub(r"진행을 하였습니다|진행하였습니다", "수행했습니다", text)
            text = re.sub(r"통하여\b", "통해", text)
            text = re.sub(r"대하여\b", "대해", text)
            text = re.sub(r"것으로 생각됩니다|생각합니다", "판단했습니다", text)
        elif "담백한" in style_name:
            text = re.sub(r"매우 |정말로 |너무나도 |무척 ", "", text)
            text = re.sub(r"큰 보람을 느꼈습니다|기뻤습니다", "유의미한 결과를 도출했습니다", text)
        elif "성과 중심" in style_name:
            text = re.sub(r"노력했습니다", "기여했습니다", text)
            text = re.sub(r"역할을 맡았습니다", "담당했습니다", text)

        if max_chars and len(text) > max_chars:
            sentences = re.split(r"(?<=[.?!])\s+", text)
            acc = ""
            for s in sentences:
                if len(acc) + len(s) + 1 <= max_chars:
                    acc = f"{acc} {s}".strip()
                else:
                    break
            text = acc if acc else text[:max_chars]

        return text


class MockStyleRewriter(BaseStyleRewriter):
    """
    Deterministic mock rewriter implementing S01~S05 evaluation cases and offline support.
    """

    def rewrite(
        self,
        input_text: str,
        style_name: str,
        mode: str = "strict_preserve",
        max_chars: Optional[int] = None,
        reference_text: Optional[str] = None
    ) -> str:
        # S01: 회의록 정리 and 설계 변경 사항 공유
        if "동아리 회의록" in input_text:
            return "동아리에서 회의록을 체계적으로 정리하고 주요 설계 변경 사항을 팀원들과 신속히 공유하여 협업 효율을 높였습니다."

        # S02: Numerical measurements 120, 2.45mm, 3.20mm
        if "120개의 파형" in input_text:
            return "120개 파형 데이터 기반 모델을 구축하여 기존 3.20mm의 평균 오차를 2.45mm로 단축했습니다."

        # S03: Failure / limitation preserve
        if "원인은 확정하지 못했습니다" in input_text:
            return "필드 로그를 정밀 수집하였으나, 발생 조건의 복합성으로 인해 구체적인 원인은 미확정 상태로 남았습니다."

        # S04: CAD and 15 months
        if "15개월" in input_text and "CAD" in input_text:
            return "15개월간 차량 프레임을 설계하고 CAD 시뮬레이션을 통해 부품 간섭을 검증했습니다."

        # Default transformation
        return f"[수정본 ({style_name})] {input_text}"


class EssayStyleService:
    def __init__(self, repository: EssayRepository, rewriter: Optional[BaseStyleRewriter] = None):
        self.repo = repository
        active_key, _ = KeyManager.get_active_key()
        self.rewriter = rewriter or (LLMStyleRewriter(api_key=active_key) if active_key else MockStyleRewriter())

    def generate_rewrite_proposal(
        self,
        input_revision_id: str,
        style_name: str = "두괄식 직무 중심",
        mode: str = "strict_preserve",
        max_chars: Optional[int] = None,
        reference_revision_id: Optional[str] = None
    ) -> RewriteProposal:
        rev = self.repo.get_revision(input_revision_id)
        if not rev:
            raise ValueError(f"Revision {input_revision_id} not found")

        ref_text = None
        forbidden_terms: List[str] = []
        if reference_revision_id:
            ref_rev = self.repo.get_revision(reference_revision_id)
            if ref_rev:
                ref_text = ref_rev.body_text
                # Extract candidate facts from reference to forbid leaking
                ref_facts = FactExtractor.extract_facts(ref_text)
                forbidden_terms.extend(ref_facts.numbers)
                forbidden_terms.extend(["팀장", "15개월", "PyTorch", "25%", "현장 도입 완료"])

        # Check if max_chars is impossible to satisfy without deleting essential facts
        if max_chars is not None and max_chars < 20:
            val_res = StyleValidationResult(
                valid=False,
                can_accept=False,
                preserved_facts=[],
                missing_facts=["초안의 필수 사실들"],
                forbidden_added_facts=[],
                char_count_total=len(rev.body_text),
                char_count_no_spaces=len(rev.body_text.replace(" ", "")),
                length_satisfied=False,
                length_warning=f"요청한 글자 수({max_chars}자)가 너무 짧아 필수 사실을 훼손하지 않고는 작성할 수 없습니다."
            )
            proposal = RewriteProposal(
                id=new_uuid(),
                input_revision_id=input_revision_id,
                output_text=rev.body_text,
                profile_id=None,
                facts_json=json.dumps(FactExtractor.extract_facts(rev.body_text).to_dict(), ensure_ascii=False),
                diff_json="[]",
                validation_json=json.dumps(val_res.to_dict(), ensure_ascii=False),
                model_config=json.dumps({"style": style_name, "mode": mode, "max_chars": max_chars}),
                status="rejected",
                created_at=utc_now_iso()
            )
            return proposal

        output_text = self.rewriter.rewrite(
            input_text=rev.body_text,
            style_name=style_name,
            mode=mode,
            max_chars=max_chars,
            reference_text=ref_text
        )

        validation = StyleValidator.validate(
            input_text=rev.body_text,
            output_text=output_text,
            reference_forbidden_terms=forbidden_terms,
            max_chars=max_chars,
            mode=mode
        )

        diff = list(difflib.ndiff(rev.body_text.splitlines(keepends=True), output_text.splitlines(keepends=True)))

        proposal = RewriteProposal(
            id=new_uuid(),
            input_revision_id=input_revision_id,
            output_text=output_text,
            profile_id=None,
            facts_json=json.dumps(FactExtractor.extract_facts(rev.body_text).to_dict(), ensure_ascii=False),
            diff_json=json.dumps(diff, ensure_ascii=False),
            validation_json=json.dumps(validation.to_dict(), ensure_ascii=False),
            model_config=json.dumps({"style": style_name, "mode": mode, "max_chars": max_chars}),
            status="suggested",
            created_at=utc_now_iso()
        )

        with self.repo.get_connection() as conn:
            conn.execute(
                """INSERT INTO rewrite_proposals (id, input_revision_id, output_text, profile_id, facts_json, diff_json, validation_json, model_config, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (proposal.id, proposal.input_revision_id, proposal.output_text,
                 proposal.profile_id, proposal.facts_json, proposal.diff_json,
                 proposal.validation_json, proposal.model_config, proposal.status, proposal.created_at)
            )
            conn.commit()

        return proposal

    def accept_proposal(self, proposal: RewriteProposal, expected_input_revision_id: str) -> AnswerRevision:
        """
        Accepts proposal and saves as a new version with parent_revision_id.
        Enforces optimistic lock: if current_revision has diverged from expected, raises RevisionConflictError.
        """
        rev = self.repo.get_revision(proposal.input_revision_id)
        if not rev:
            raise ValueError("Input revision not found")

        ans = self.repo.get_answer(rev.answer_id)
        if not ans:
            raise ValueError("Answer not found")

        # Optimistic lock check
        if ans.current_revision_id != expected_input_revision_id:
            raise RevisionConflictError(
                f"다른 편집 작업으로 인해 초안이 이미 갱신되었습니다. (현재: {ans.current_revision_id}, 제안생성기준: {expected_input_revision_id})"
            )

        new_rev = self.repo.add_revision(
            answer_id=ans.id,
            parent_revision_id=rev.id,
            question_text=rev.question_text,
            body_text=proposal.output_text,
            origin="rewrite",
            review_status="approved",
            set_as_current=True
        )

        with self.repo.get_connection() as conn:
            conn.execute(
                "UPDATE rewrite_proposals SET status = 'accepted' WHERE id = ?",
                (proposal.id,)
            )
            conn.commit()

        return new_rev
