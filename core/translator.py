"""
Multi-Engine Academic Neural & LLM Translation Architecture
Supports Google's free web translation, Google Gemini (3.7 / 3.5 / 2.5 Flash), OpenAI GPT-4o-mini, Claude 3.5 Haiku, and DeepL.
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

입력된 각 문단(paragraphs)의 순서와 개수를 1:1로 정확히 유지하여, key가 'translations'인 JSON 객체(번역된 한국어 문자열 배열)로만 응답해 줘."""


class GoogleBlockedError(Exception):
    """Google's free endpoints refused this client (redirect to its 'sorry' page, or rate limit after retries)."""


class PaperTranslator:
    """Multi-Engine Batch Translation Engine supporting Free Zero-Key, Gemini 3.7 Flash, OpenAI, Claude, and DeepL."""

    SUPPORTED_ENGINES = [
        "⚡️ Google Neural (무료 · 무제한)",
        "🤖 Google Gemini 3.7 Flash (최신 고성능 학술 AI · API 키 필요)",
        "🤖 Google Gemini 3.5 Flash (고성능 학술 AI · API 키 필요)"
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

    @staticmethod
    def _translation_list(candidate: str) -> Optional[List[str]]:
        """The translation strings of a JSON object or array, or None when nothing decodes."""
        for pattern in (None, r'\{[\s\S]*\}', r'\[[\s\S]*\]'):
            match = re.search(pattern, candidate) if pattern else None
            if pattern and not match:
                continue
            try:
                parsed = json.loads(match.group(0) if match else candidate)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                for key in ("translations", "korean_translations", "results", "data", "paragraphs"):
                    if isinstance(parsed.get(key), list):
                        return [str(item).strip() for item in parsed[key]]
                if parsed and all(str(k).isdigit() for k in parsed):
                    return [str(parsed[str(i)]).strip() for i in range(1, len(parsed) + 1) if str(i) in parsed]
            elif isinstance(parsed, list):
                return [str(item).strip() for item in parsed]
        return None

    @classmethod
    def _parse_json_translations(cls, text_out: str, expected_count: int) -> List[str]:
        """
        Parses the model's translation list.
        LaTeX with single backslashes is repaired before decoding (otherwise \\text turns into a tab and
        \\odot makes the JSON invalid), and a response cut off by the output limit keeps its complete
        items. Undecodable JSON is a failed attempt, never shown as a translation.
        """
        cleaned = text_out.strip()
        if "```" in cleaned:
            code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned, re.IGNORECASE)
            if code_block_match:
                cleaned = code_block_match.group(1).strip()
        repaired = cls._repair_latex_backslashes(cleaned)

        for candidate in dict.fromkeys((repaired, cleaned)):
            found = cls._translation_list(candidate)
            if found is not None:
                return found

        start = re.search(r'"translations"\s*:\s*\[', repaired)
        if start:
            items = []
            for literal in re.finditer(r'"(?:[^"\\]|\\.)*"', repaired[start.end():]):
                try:
                    items.append(str(json.loads(literal.group(0))).strip())
                except ValueError:
                    break
            if items:
                return items

        if cleaned.startswith(("{", "[")):
            return []

        # Plain-text answer: numbered lines or one paragraph per line.
        lines = [re.sub(r'^(?:\[\d+\]|\d+[\.\)]|\-\s*)\s*', '', line.strip()).strip() for line in cleaned.splitlines()]
        return [line for line in lines if line]

    # Gemini models the stored key can call (ListModels, 2026-09); the engine's own model is tried first.
    GEMINI_MODELS = ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-2.5-flash"]

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

        user_content = json.dumps({
            "paper_title": paper_title,
            "paragraphs": texts
        }, ensure_ascii=False)

        full_prompt = f"{custom_prompt}\n\n[번역할 본문 데이터]:\n{user_content}"
        payload = {
            "contents": [
                {
                    "parts": [{"text": full_prompt}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.15,
                "maxOutputTokens": 16384
            }
        }
        # The key travels in a header, so it never appears in a URL or an error message.
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

        errors = []
        for model_id in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
            for attempt in range(2):
                try:
                    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                except urllib.error.HTTPError as he:
                    err_body = he.read().decode("utf-8", errors="ignore")
                    if he.code == 403:
                        raise RuntimeError("Gemini 번역 실패: API 키 권한 없음 (HTTP 403)")
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
                translations = cls._parse_json_translations(text_out, expected_count=len(texts)) if text_out else []
                if not translations:
                    errors.append(f"{model_id}: 응답을 해석하지 못함")
                    break
                pairs = VisualHighlighter.align_translation_pairs(
                    extracted_texts=texts,
                    translated_texts=translations,
                    blocks=blocks
                )
                for pair in pairs[len(translations):]:
                    pair["untranslated"] = True
                return pairs, model_id

        raise RuntimeError(f"Gemini 번역 실패: {'; '.join(errors[-2:])}")

    @classmethod
    def _translate_with_openai(
        cls,
        texts: List[str],
        blocks: List[Dict[str, Any]],
        paper_title: str,
        api_key: str,
        custom_prompt: str
    ) -> Optional[List[Dict[str, Any]]]:
        endpoint = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": custom_prompt},
                {"role": "user", "content": json.dumps({"paper_title": paper_title, "paragraphs": texts}, ensure_ascii=False)}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }
        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            translations = cls._parse_json_translations(content, expected_count=len(texts))
            return VisualHighlighter.align_translation_pairs(
                extracted_texts=texts,
                translated_texts=translations,
                blocks=blocks
            )

    @classmethod
    def _translate_with_claude(
        cls,
        texts: List[str],
        blocks: List[Dict[str, Any]],
        paper_title: str,
        api_key: str,
        custom_prompt: str
    ) -> Optional[List[Dict[str, Any]]]:
        endpoint = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 2048,
            "system": custom_prompt,
            "messages": [
                {"role": "user", "content": f"Translate these paragraphs into JSON with key 'translations':\n{json.dumps(texts, ensure_ascii=False)}"}
            ]
        }
        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content_text = data["content"][0]["text"].strip()
            translations = cls._parse_json_translations(content_text, expected_count=len(texts))
            return VisualHighlighter.align_translation_pairs(
                extracted_texts=texts,
                translated_texts=translations,
                blocks=blocks
            )

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

    @classmethod
    def _translate_with_deepl(cls, texts: List[str], blocks: List[Dict[str, Any]], api_key: str) -> Optional[List[Dict[str, Any]]]:
        endpoint = "https://api-free.deepl.com/v2/translate" if api_key.endswith(":fx") else "https://api.deepl.com/v2/translate"
        headers = {
            "Authorization": f"DeepL-Auth-Key {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "text": texts,
            "target_lang": "KO",
            "source_lang": "EN"
        }
        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translations_raw = data.get("translations", [])
            translated_list = [item.get("text", "") for item in translations_raw]
            return VisualHighlighter.align_translation_pairs(
                extracted_texts=texts,
                translated_texts=translated_list,
                blocks=blocks
            )

    @classmethod
    def _is_valid_deepl_key(cls, key: str) -> bool:
        if not key or len(key) < 20:
            return False
        if key.endswith(":fx") or re.match(r'^[a-f0-9\-]{30,45}(:fx)?$', key.lower()):
            return True
        return False
