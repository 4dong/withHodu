"""
Multi-Engine Academic Neural & LLM Translation Architecture
Google's free web translation, or Google Gemini 3.8 Flash (3.7 / 3.6 as quota fallbacks).
Full custom prompt engineering support for all LLM models.
"""

import os
import json
import html
import urllib.request
import urllib.parse
import urllib.error
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from core import rate_limit
from core.math_formatter import AcademicMathFormatter
from core.key_manager import KeyManager
from core.visual_highlighter import VisualHighlighter

DEFAULT_ACADEMIC_PROMPT = """너는 세계 최고 수준의 전문 학술 번역가이자 해당 분야의 AI/컴퓨터공학 연구원이야. 업로드된 논문 텍스트를 바탕으로 다음 지침에 맞춰 최상의 한국어 학술 번역을 제공해 줘.

1. 수식 및 수학 기호 보존 원칙 (최우선):
- 본문 및 수식 블록에 등장하는 모든 수식, 변수, 함수, 기호, 첨자, 그리스 문자(예: $\\hat{A}^i, \\hat{x}_1^i, v_\\theta(x_t, t), \\lambda_1, \\sigma^2, \\Delta t, x_t, \\mathbb{R}^d, \\mathcal{L}$ 등)는 절대로 한글 음역(예: '람다1', '시그마 제곱', '세타')이나 깨진 텍스트로 바꾸지 말고, 반드시 표준 LaTeX 인라인 수식 `$수식$` 또는 독립 수식 `$$수식$$` 형태로 정확하게 출력할 것.
- 수식 기호 뒤의 한국어 조사(은/는/이/가/을/를/의/에/와/과/로/으로/에서)는 반드시 닫는 달러 기호($) 바깥에 작성할 것 (올바른 예: '$x_t$는', '$v_\\theta$'의, '$\\theta$에' / 잘못된 예: '$\\text{xt는}$', '$x_t는$').
- 수식 번호(예: (1), (2), (3))와 위첨자/아래첨자(Subscript/Superscript)가 누락되지 않도록 완전한 수식 형태로 출력할 것.
- JSON 문자열 내의 LaTeX 역슬래시는 유효한 JSON 형식에 맞춰 `\\\\`로 이스케이프할 것 (예: `\\\\theta`, `\\\\frac`).

2. 번역 원칙:
- 직역을 피하고 자연스럽고 유려한 학술적 한국어 문장으로 번역할 것.
- 전문 용어, 기술 명칭, 지표(Metric), 약어(예: CNN, Transformer, Pass@k, Flow Matching 등)는 억지로 한글화하지 말고 괄호 안에 영어 원문을 병기할 것 (예: 가중치 앙상블(Weight Ensembling), 인공신경망(Artificial Neural Network)).

3. 번역 톤:
- 객관적이고 격식 있는 학술 논문 어조를 유지할 것.
- 문장 끝은 논문 전체에서 '~합니다/~입니다'체로 통일할 것 (쪽마다 따로 번역되므로 '~한다'체와 섞이지 않게).
- 원문의 'we'는 '우리는'으로 직역하지 말고 '본 연구에서는' 등으로 자연스럽게 옮기거나 생략할 것."""


class GoogleBlockedError(Exception):
    """Google's free endpoints refused this client (redirect to its 'sorry' page, or rate limit after retries)."""


class PaperTranslator:
    """Translates one page at a time with free Google translation or Gemini."""

    SUPPORTED_ENGINES = [
        "⚡️ Google Neural (무료 · 무제한)",
        "🤖 Google Gemini 3.8 Flash (최신 고성능 학술 AI · API 키 필요)",
    ]

    @classmethod
    def translate_single_page(
        cls,
        page_data: Dict[str, Any],
        paper_title: str = "",
        engine: str = "⚡️ Google Neural (무료 · 무제한)",
        custom_api_key: Optional[str] = None,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Translates the paragraphs of one page: Gemini takes the page in one request, Google in newline-joined
        batches (see _translate_with_google). Paragraphs left untranslated are counted in failed_count.
        """
        blocks = page_data.get("blocks", [])
        if not blocks:
            paragraphs = page_data.get("paragraphs", [])
            blocks = [{"text": p, "bbox": {"top": "0%", "left": "0%", "width": "100%", "height": "0%"}} for p in paragraphs]

        page_num = page_data.get("page_num", 1)
        stitched_prefix = page_data.get("stitched_prefix", "").strip()

        # Display formulas are shown as the original rendering, never translated; they rejoin the pairs in page order.
        page_blocks = blocks
        blocks = [b for b in page_blocks if b.get("kind") != "equation"]
        if not blocks:
            return cls._with_formulas({
                "page_num": page_num,
                "engine": "원본 수식" if page_blocks else "Empty Page",
                "is_fallback": False,
                "target_engine": engine,
                "pairs": []
            }, page_blocks)

        # Seamless cross-page sentence stitching
        extracted_texts = [b["text"] for b in blocks]
        if stitched_prefix and extracted_texts:
            extracted_texts[0] = f"{stitched_prefix} {extracted_texts[0]}"
            blocks[0]["text"] = extracted_texts[0]

        prompt_to_use = custom_prompt or DEFAULT_ACADEMIC_PROMPT
        result = None

        # Engine Option 2: Google Gemini (3.7 / 3.5 / 2.5 Flash)
        if "Gemini" in engine:
            effective_key = custom_api_key
            if not effective_key or len(str(effective_key).strip()) < 15:
                active_k, _ = KeyManager.get_active_key()
                effective_key = active_k or os.environ.get("GEMINI_API_KEY", "")

            last_error_msg = ""
            if effective_key and len(str(effective_key).strip()) > 15:
                try:
                    pairs, used_model = cls._translate_with_gemini(
                        texts=extracted_texts,
                        blocks=blocks,
                        paper_title=paper_title,
                        api_key=str(effective_key).strip(),
                        custom_prompt=prompt_to_use,
                        preferred_model=cls._gemini_model_for(engine)
                    )
                    if pairs:
                        result = {
                            "page_num": page_num,
                            "engine": f"Google Gemini ({used_model})",
                            "model_used": used_model,
                            "is_fallback": False,
                            "pairs": pairs
                        }
                except Exception as e:
                    last_error_msg = str(e)
                    print(f"Gemini translation error: {e}")

            if not result:
                fallback_reason = last_error_msg if last_error_msg else "Gemini API 키가 등록되지 않았습니다."
                result = cls._translate_with_google(
                    extracted_texts,
                    blocks,
                    page_num,
                    fallback_note="Google 신경망 (Gemini 미작동 폴백)"
                )
                result["is_fallback"] = True
                result["fallback_reason"] = fallback_reason

        # Engine Option 1 (Default): Google's free web translation, batched per page
        else:
            result = cls._translate_with_google(extracted_texts, blocks, page_num)
            result["is_fallback"] = False

        # Post-processing: an LLM already writes LaTeX, so its output only gets delimiter and formula
        # cleanup; Google output needs the heuristics that rebuild math from transliterated symbols.
        if result and "pairs" in result:
            result["target_engine"] = engine
            result["page_num"] = page_num
            # Paragraphs still showing their source text; the reader translates such a page again later.
            result["failed_count"] = sum(1 for p in result["pairs"] if p.get("untranslated"))
            result["translated_at"] = time.time()
            normalize = (AcademicMathFormatter.normalize_llm_math if result.get("model_used")
                         else AcademicMathFormatter.format_math_in_text)
            for p in result["pairs"]:
                if p.get("ko"):
                    try:
                        p["ko"] = normalize(p["ko"])
                    except Exception as e:
                        print(f"Math post-processing defensive catch: {e}")

        return cls._with_formulas(result, page_blocks)

    @staticmethod
    def _with_formulas(result: Dict[str, Any], page_blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Places formula pairs (original renderings) between the translated pairs in page order, renumbered."""
        if not result or "pairs" not in result or not any(b.get("kind") == "equation" for b in page_blocks):
            return result
        translated = iter(result["pairs"])
        pairs = []
        for block in page_blocks:
            if block.get("kind") == "equation":
                pairs.append({"en": "", "ko": "", "kind": "equation", "bbox": block.get("bbox"),
                              "image_path": block.get("image_path"), "image_width_pt": block.get("image_width_pt"),
                              "source_text": block.get("text", "")})
            else:
                pair = next(translated, None)
                if pair is not None:
                    pairs.append(pair)
        pairs.extend(translated)
        for index, pair in enumerate(pairs, 1):
            pair["id"] = index
        result["pairs"] = pairs
        return result

    # JSON escapes that really start a LaTeX command (\\text, \\frac, \\beta, \\nabla, \\rho, \\odot, \\{).
    # Kept as JSON: escaped backslashes, unicode escapes, quotes, and \\b \\f \\n \\r \\t not followed by a letter.
    _JSON_ESCAPE = re.compile(r'\\\\|\\u[0-9a-fA-F]{4}|\\["/]|\\[bfnrt](?![A-Za-z])|\\')

    @classmethod
    def _repair_latex_backslashes(cls, raw: str) -> str:
        """Doubles lone backslashes so LaTeX written with single backslashes survives json.loads."""
        return cls._JSON_ESCAPE.sub(lambda m: m.group(0) if len(m.group(0)) > 1 else "\\\\", raw)

    @classmethod
    def _keyed_translations(cls, text_out: str, ids: List[str]) -> Optional[List[str]]:
        """Translation for each paragraph id, "" where the reply has none; None when the reply is not an object."""
        cleaned = text_out.strip()
        repaired = cls._repair_latex_backslashes(cleaned)
        for candidate in dict.fromkeys((cleaned, repaired)):
            try:
                parsed = json.loads(candidate)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                return [str(parsed.get(i) or "").strip() for i in ids]
        # A reply cut off by the output limit still holds its complete "pN": "..." items.
        found = {}
        for key, literal in re.findall(r'"(p\d+)"\s*:\s*("(?:[^"\\]|\\.)*")', repaired):
            try:
                found[key] = str(json.loads(literal)).strip()
            except ValueError:
                break
        return [found.get(i, "") for i in ids] if found else None

    # Model -> thinking level. Measured 2026-09-23 on the densest pages in the library (up to 5,500 characters):
    # default thinking spent 4-20x the answer on thought tokens, 16-45 s a page, and could use up
    # maxOutputTokens before the answer ended. On "low" every page came back whole in 5-15 s. 3.8 and 3.7 cost
    # the same; 3.8 was faster with keyed output (7.4 s vs 9.2 s mean) and read more naturally, so it is the one
    # translation model and the others only take over on a quota limit. 3.7/3.8 reject "minimal";
    # gemini-2.5-flash is closed to this key (404).
    GEMINI_MODELS = {"gemini-3.8-flash": "low", "gemini-3.7-flash": "low", "gemini-3.6-flash": "minimal"}

    # Owned by the code, not the editable prompt. Answering a list by position let the model drop or merge a
    # short paragraph (a formula line, "The final objective is:") in ~1 of 10 pages, which shifted every later
    # translation onto the wrong paragraph; one required key per paragraph keeps each answer on its source.
    GEMINI_OUTPUT_RULES = ("[응답 형식]\n입력 paragraphs의 key(p1, p2, ...)마다 그 문단 하나의 번역을 같은 key에 넣은 "
                           "JSON 객체로만 응답할 것. 짧은 제목이나 수식 한 줄도 하나의 문단이며, 문단을 합치거나 빼거나 나누지 말 것.")

    @staticmethod
    def _gemini_model_for(engine: str) -> Optional[str]:
        match = re.search(r"Gemini (\d+(?:\.\d+)?) Flash", engine or "")
        return f"gemini-{match.group(1)}-flash" if match else None

    @classmethod
    def _translate_with_gemini(
        cls,
        texts: List[str],
        blocks: List[Dict[str, Any]],
        paper_title: str,
        api_key: str,
        custom_prompt: str,
        preferred_model: Optional[str] = None
    ) -> Tuple[Optional[List[Dict[str, Any]]], str]:
        """
        Translates one page in one request. Moves to the next model on a quota limit (429), a missing model
        (404), a timeout or an unreadable reply; retries a model once after an overload (5xx); stops at a
        rejected request (400, 403), which every model would reject the same way. Paragraphs missing from
        the reply are marked untranslated.
        """
        models_to_try = list(cls.GEMINI_MODELS)
        if preferred_model in models_to_try:
            models_to_try.remove(preferred_model)
            models_to_try.insert(0, preferred_model)

        ids = [f"p{i + 1}" for i in range(len(texts))]
        user_content = json.dumps({"paper_title": paper_title, "paragraphs": dict(zip(ids, texts))}, ensure_ascii=False)
        full_prompt = f"{custom_prompt}\n\n{cls.GEMINI_OUTPUT_RULES}\n\n[번역할 본문 데이터]:\n{user_content}"
        schema = {"type": "object", "properties": {i: {"type": "string"} for i in ids},
                  "required": ids, "propertyOrdering": ids}
        # The key travels in a header, so it never appears in a URL or an error message.
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

        errors = []
        for model_id in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
            payload = {
                "contents": [{"parts": [{"text": full_prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": schema,
                    "temperature": 0.15,
                    "maxOutputTokens": 16384,
                    "thinkingConfig": {"thinkingLevel": cls.GEMINI_MODELS[model_id]},
                },
            }
            for attempt in range(2):
                try:
                    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                except urllib.error.HTTPError as he:
                    err_body = he.read().decode("utf-8", errors="ignore")
                    if he.code == 403:
                        raise RuntimeError("Gemini 번역 실패: API 키 권한 없음 (HTTP 403)")
                    if he.code == 400 and "thinking" in err_body.lower():
                        errors.append(f"{model_id}: 생각 수준 미지원 (HTTP 400)")
                        break
                    if he.code == 400:
                        raise RuntimeError(f"Gemini 번역 실패: 요청 거부 (HTTP 400 - {err_body[:80]})")
                    if he.code >= 500 and attempt == 0:
                        time.sleep(2)
                        continue
                    reason = {404: "모델 미지원 (HTTP 404)", 429: "사용량 한도 초과 (HTTP 429)"}.get(he.code, f"HTTP {he.code}")
                    errors.append(f"{model_id}: {reason}")
                    break
                except Exception as e:
                    errors.append(f"{model_id}: {e}")
                    break

                candidates = data.get("candidates", [])
                parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
                text_out = parts[0].get("text", "").strip() if parts else ""
                keyed = cls._keyed_translations(text_out, ids) if text_out else None
                if not keyed or not any(keyed):
                    errors.append(f"{model_id}: 응답을 해석하지 못함")
                    break
                pairs = VisualHighlighter.align_translation_pairs(
                    extracted_texts=texts,
                    translated_texts=[ko or en for ko, en in zip(keyed, texts)],
                    blocks=blocks
                )
                for pair, ko in zip(pairs, keyed):
                    if not ko:
                        pair["untranslated"] = True
                return pairs, model_id

        raise RuntimeError(f"Gemini 번역 실패: {'; '.join(errors[-2:])}")

    GOOGLE_GTX_URL = "https://translate.googleapis.com/translate_a/single"
    GOOGLE_MOBILE_URL = "https://translate.google.com/m"
    # One typical page fits in one request (a Qwen-Audio page carries at most ~3,800 characters).
    GOOGLE_BATCH_CHARS = 4500
    GOOGLE_COOLDOWN_SECONDS = 300

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        """Google answers a client it limits with a redirect to its 'sorry' page; surface that instead of following it."""
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    _google_opener = urllib.request.build_opener(_NoRedirect)

    @classmethod
    def _google_fetch(cls, request: urllib.request.Request, timeout: float) -> str:
        """
        Sends one request to a Google translate endpoint. 429 and 5xx wait and retry (Retry-After up to 10 s,
        otherwise 1 s then 2 s). The 'sorry' redirect, or a 429 on the last try, blocks Google for
        GOOGLE_COOLDOWN_SECONDS: both endpoints are refused together, so nothing more is sent until then. The
        deadline lives in core.rate_limit, which survives the module reload app.py does on every run.
        """
        if time.time() < rate_limit.google_blocked_until:
            raise GoogleBlockedError()
        for attempt in range(3):
            try:
                with cls._google_opener.open(request, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="ignore")
            except urllib.error.HTTPError as e:
                if 300 <= e.code < 400 or (e.code == 429 and attempt == 2):
                    rate_limit.google_blocked_until = time.time() + cls.GOOGLE_COOLDOWN_SECONDS
                    raise GoogleBlockedError() from e
                if not (e.code == 429 or e.code >= 500) or attempt == 2:
                    raise
                retry_after = (e.headers or {}).get("Retry-After") or ""
                time.sleep(min(float(retry_after), 10) if retry_after.isdigit() else 2 ** attempt)
        raise RuntimeError("unreachable")

    @classmethod
    def _google_gtx(cls, text: str) -> str:
        data = urllib.parse.urlencode({"client": "gtx", "sl": "en", "tl": "ko", "dt": "t", "q": text}).encode("utf-8")
        request = urllib.request.Request(cls.GOOGLE_GTX_URL, data=data,
                                         headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
        reply = json.loads(cls._google_fetch(request, timeout=10))
        return "".join(part[0] for part in reply[0] if part and part[0])

    @classmethod
    def _google_mobile(cls, text: str) -> Optional[str]:
        url = cls.GOOGLE_MOBILE_URL + "?" + urllib.parse.urlencode({"sl": "en", "tl": "ko", "q": text})
        request = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        })
        match = re.search(r'<div class="result-container">([\s\S]*?)</div>', cls._google_fetch(request, timeout=8))
        return html.unescape(match.group(1)).strip() if match else None

    @classmethod
    def _translate_google_paragraph(cls, text: str) -> Optional[str]:
        """One paragraph: gtx, then the mobile page when gtx fails for a reason other than a block."""
        for translate in (cls._google_gtx, cls._google_mobile):
            try:
                translated = translate(text)
            except GoogleBlockedError:
                raise
            except Exception as e:
                print(f"Google translation error ({translate.__name__}): {e}")
                continue
            if translated and translated.strip():
                return translated.strip()
        return None

    @classmethod
    def _google_batches(cls, texts: List[str]) -> List[List[int]]:
        """Indices of the non-empty paragraphs, grouped so each newline-joined request stays within GOOGLE_BATCH_CHARS."""
        batches, current, size = [], [], 0
        for index, text in enumerate(texts):
            if not text:
                continue
            if current and size + len(text) + 1 > cls.GOOGLE_BATCH_CHARS:
                batches.append(current)
                current, size = [], 0
            current.append(index)
            size += len(text) + 1
        if current:
            batches.append(current)
        return batches

    @classmethod
    def _translate_with_google(cls, extracted_texts: List[str], blocks: List[Dict[str, Any]], page_num: int, fallback_note: Optional[str] = None) -> Dict[str, Any]:
        """
        Translates a page with Google's free web endpoints in as few requests as possible. Paragraphs are
        joined with newlines and sent together, one request for a typical page; the reply is split back on
        newlines and kept only if it yields the same number of non-empty paragraphs, otherwise that batch
        goes paragraph by paragraph. Once Google blocks the client nothing more is sent: the remaining
        paragraphs keep their source text and are marked untranslated.
        """
        texts = [re.sub(r"\s+", " ", text).strip() for text in extracted_texts]
        translations: List[Optional[str]] = ["" if not text else None for text in texts]
        failure_reason = ""
        unreachable = False
        try:
            for batch in cls._google_batches(texts):
                joined = None
                if len(batch) > 1:
                    try:
                        parts = cls._google_gtx("\n".join(texts[i] for i in batch)).strip().split("\n")
                        if len(parts) == len(batch) and all(part.strip() for part in parts):
                            joined = [part.strip() for part in parts]
                    except GoogleBlockedError:
                        raise
                    except urllib.error.HTTPError as e:
                        print(f"Google batch translation error: {e}")
                    except (urllib.error.URLError, OSError) as e:
                        # No connection: asking again paragraph by paragraph would only wait out more timeouts.
                        print(f"Google batch translation error: {e}")
                        unreachable = True
                        continue
                    except Exception as e:
                        print(f"Google batch translation error: {e}")
                if joined is not None:
                    for index, translated in zip(batch, joined):
                        translations[index] = translated
                else:
                    for index in batch:
                        translations[index] = cls._translate_google_paragraph(texts[index])
        except GoogleBlockedError:
            failure_reason = "Google 번역이 요청을 잠시 막았어요. 몇 분 뒤 다시 시도하거나 사이드바에서 Gemini 엔진을 선택하세요."

        failed = [index for index, translated in enumerate(translations) if translated is None]
        if failed and not failure_reason:
            failure_reason = "Google 번역에 연결하지 못했어요." if unreachable else "Google 번역 응답을 받지 못했어요."
        pairs = VisualHighlighter.align_translation_pairs(
            extracted_texts=extracted_texts,
            translated_texts=[t if t is not None else extracted_texts[i].strip() for i, t in enumerate(translations)],
            blocks=blocks
        )
        for index in failed:
            pairs[index]["untranslated"] = True

        return {
            "page_num": page_num,
            "engine": fallback_note if fallback_note else "Google 번역 (무료 웹)",
            "pairs": pairs,
            "failure_reason": failure_reason
        }

