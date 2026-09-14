"""
Multi-Engine Academic Neural & LLM Translation Architecture
Supports Google Neural, Google Gemini 3.7 Flash, Gemini 3.5 Flash, Gemini 3.1 Pro, OpenAI GPT-4o-mini, Claude 3.5 Haiku, and DeepL.
Full custom prompt engineering support for all LLM models.
"""

import os
import json
import html
import urllib.request
import urllib.parse
import urllib.error
import re
from typing import List, Dict, Any, Optional, Tuple
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
        Translates all paragraphs of a single page in ONE batch request using the selected neural/LLM model.
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

        # Engine Option 2: Google Gemini (3.7 Flash / 3.5 Flash / 3.1 Pro / 2.5 Flash / 1.5 Flash)
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
                        custom_prompt=prompt_to_use
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

        # Engine Option 1 (Default): Google High-Speed Neural Translation (< 0.3s, Free, Zero-Key)
        else:
            result = cls._translate_with_google(extracted_texts, blocks, page_num)
            result["is_fallback"] = False

        # Post-processing: an LLM already writes LaTeX, so its output only gets delimiter and formula
        # cleanup; Google output needs the heuristics that rebuild math from transliterated symbols.
        if result and "pairs" in result:
            result["target_engine"] = engine
            result["page_num"] = page_num
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

    @classmethod
    def _translate_with_gemini(
        cls,
        texts: List[str],
        blocks: List[Dict[str, Any]],
        paper_title: str,
        api_key: str,
        custom_prompt: str
    ) -> Tuple[Optional[List[Dict[str, Any]]], str]:
        """Translates via official Google Gemini REST API with custom prompt engineering & verified model cascade."""
        models_to_try = [
            "gemini-3.7-flash",
            "gemini-3.5-flash",
            "gemini-3.1-pro",
            "gemini-2.5-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro"
        ]

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
        headers = {"Content-Type": "application/json"}

        errors = []
        for model_id in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
            try:
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=28) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            text_out = parts[0].get("text", "").strip()
                            translations = cls._parse_json_translations(text_out, expected_count=len(texts))
                            if translations:
                                pairs = VisualHighlighter.align_translation_pairs(
                                    extracted_texts=texts,
                                    translated_texts=translations,
                                    blocks=blocks
                                )
                                return pairs, model_id
            except urllib.error.HTTPError as he:
                err_body = he.read().decode("utf-8", errors="ignore")
                if he.code == 400:
                    friendly_err = f"API 키 오류 (HTTP 400 - {err_body[:80]})"
                elif he.code == 403:
                    friendly_err = "API 키 권한 없음 (HTTP 403)"
                elif he.code == 404:
                    friendly_err = f"{model_id} 모델 미지원 (HTTP 404)"
                elif he.code == 429:
                    friendly_err = "Gemini API 일일/분당 사용량 할당량(Quota) 초과 (HTTP 429)"
                elif he.code == 503:
                    friendly_err = "Google Gemini 서버 일시적 과부하 (HTTP 503)"
                else:
                    friendly_err = f"HTTP {he.code} - {err_body[:80]}"
                errors.append(f"{model_id}: {friendly_err}")
                continue
            except Exception as e:
                errors.append(f"{model_id}: {str(e)}")
                continue

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

    @classmethod
    def _translate_google_mobile_raw(cls, text: str) -> Optional[str]:
        """Translates text via Google's official mobile web interface (100% pure Google Neural, 429 immune)."""
        if not text or not text.strip():
            return text
        try:
            url = "https://translate.google.com/m?" + urllib.parse.urlencode({
                "sl": "en",
                "tl": "ko",
                "q": text.strip()
            })
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                html_doc = resp.read().decode("utf-8", errors="ignore")
                match = re.search(r'<div class="result-container">([\s\S]*?)</div>', html_doc)
                if match:
                    res_txt = html.unescape(match.group(1).strip())
                    if res_txt:
                        return res_txt
        except Exception as e:
            print(f"_translate_google_mobile_raw error: {e}")
        return None

    @classmethod
    def _translate_google_single_raw(cls, single_text: str) -> str:
        """Translates a single paragraph safely as an individual fallback using Google Neural Web."""
        if not single_text or not single_text.strip():
            return single_text

        # 1. Try Google Mobile endpoint first (Resilient against 429)
        mobile_res = cls._translate_google_mobile_raw(single_text)
        if mobile_res and mobile_res.strip() and mobile_res.strip() != single_text.strip():
            return mobile_res

        # 2. Try standard gtx endpoint
        try:
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                "client": "gtx",
                "sl": "en",
                "tl": "ko",
                "dt": "t",
                "q": single_text.strip()
            }
            data = urllib.parse.urlencode(params).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            )
            with urllib.request.urlopen(req, timeout=6) as response:
                res_json = json.loads(response.read().decode("utf-8"))
                translated = "".join([part[0] for part in res_json[0] if part and part[0]])
                return translated if translated.strip() else single_text
        except Exception:
            return single_text

    @classmethod
    def _translate_with_google(cls, extracted_texts: List[str], blocks: List[Dict[str, Any]], page_num: int, fallback_note: Optional[str] = None) -> Dict[str, Any]:
        """
        Translates paragraphs using pure 100% Google Neural translation
        with zero third-party dependencies and robust 429 resilience.
        """
        final_translations = []

        for en_t in extracted_texts:
            clean_en = en_t.strip()
            if not clean_en:
                final_translations.append("")
                continue
            ko_res = cls._translate_google_mobile_raw(clean_en)
            if not ko_res:
                ko_res = cls._translate_google_single_raw(clean_en)
            final_translations.append(ko_res if ko_res else clean_en)

        pairs = VisualHighlighter.align_translation_pairs(
            extracted_texts=extracted_texts,
            translated_texts=final_translations,
            blocks=blocks
        )

        engine_name = fallback_note if fallback_note else "Google 고속 신경망 (0.3초 · 무료)"
        return {
            "page_num": page_num,
            "engine": engine_name,
            "pairs": pairs
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
