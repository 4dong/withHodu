"""Request volume and failure handling for page translation, offline: Google gets a page in newline-joined
batches and stops entirely once it blocks the client; Gemini marks paragraphs missing from its reply."""

import importlib
import io
import json
import unittest
import urllib.error
import urllib.parse
from unittest import mock

import core.translator
from core import rate_limit
from core.translator import PaperTranslator

GOOGLE = PaperTranslator.SUPPORTED_ENGINES[0]
GEMINI = PaperTranslator.SUPPORTED_ENGINES[1]
BBOX = {"top": "10%", "left": "10%", "width": "80%", "height": "10%"}


def page(*texts):
    return {"page_num": 1, "blocks": [{"text": text, "bbox": BBOX} for text in texts]}


def gtx_reply(translated):
    return json.dumps([[[translated, "source"]], None, "en"])


def http_error(code, headers=None):
    return urllib.error.HTTPError("https://translate.example", code, "error", headers or {}, io.BytesIO(b""))


class FakeGoogle:
    """Stands in for the no-redirect opener; answers from a script and records every request."""

    def __init__(self, answer):
        self.answer = answer
        self.requests = []

    def open(self, request, timeout=None):
        url = request.full_url
        if request.data:
            query = urllib.parse.parse_qs(request.data.decode("utf-8"))["q"][0]
        else:
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["q"][0]
        self.requests.append((url.split("?")[0], query))
        outcome = self.answer(query, len(self.requests))
        if isinstance(outcome, Exception):
            raise outcome
        return io.BytesIO(outcome.encode("utf-8"))


class GoogleBatchTests(unittest.TestCase):
    def setUp(self):
        rate_limit.google_blocked_until = 0.0
        self.addCleanup(setattr, rate_limit, "google_blocked_until", 0.0)
        sleep = mock.patch("core.translator.time.sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)

    def use(self, answer):
        fake = FakeGoogle(answer)
        patcher = mock.patch.object(PaperTranslator, "_google_opener", fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def test_a_page_goes_out_in_one_request(self):
        google = self.use(lambda query, n: gtx_reply("첫 문단입니다.\n둘째 문단입니다.\n셋째 문단입니다."))
        result = PaperTranslator.translate_single_page(
            page("First paragraph\nwraps here.", "Second paragraph.", "Third paragraph."), engine=GOOGLE)
        self.assertEqual(len(google.requests), 1)
        # Line breaks inside a paragraph become spaces, so only paragraph boundaries are newlines.
        self.assertEqual(google.requests[0][1], "First paragraph wraps here.\nSecond paragraph.\nThird paragraph.")
        self.assertEqual([p["ko"] for p in result["pairs"]], ["첫 문단입니다.", "둘째 문단입니다.", "셋째 문단입니다."])
        self.assertEqual(result["failed_count"], 0)

    def test_a_reply_that_does_not_split_back_goes_paragraph_by_paragraph(self):
        def answer(query, n):
            return gtx_reply("합쳐진 번역" if "\n" in query else "번역: " + query)
        google = self.use(answer)
        result = PaperTranslator.translate_single_page(page("One.", "Two.", "Three."), engine=GOOGLE)
        # One batch, then one gtx request per paragraph: no second try of the same request, no mobile page.
        self.assertEqual(len(google.requests), 4)
        self.assertTrue(all(url == PaperTranslator.GOOGLE_GTX_URL for url, _ in google.requests))
        self.assertEqual([p["ko"] for p in result["pairs"]], ["번역: One.", "번역: Two.", "번역: Three."])
        self.assertEqual(result["failed_count"], 0)

    def test_a_block_stops_every_further_request(self):
        google = self.use(lambda query, n: http_error(302, {"Location": "https://www.google.com/sorry/index"}))
        first = PaperTranslator.translate_single_page(page("One.", "Two.", "Three."), engine=GOOGLE)
        self.assertEqual(len(google.requests), 1)
        self.assertEqual(first["failed_count"], 3)
        self.assertIn("막았어요", first["failure_reason"])
        self.assertEqual([p["ko"] for p in first["pairs"]], ["One.", "Two.", "Three."])

        # The next page inside the cool-down sends nothing.
        second = PaperTranslator.translate_single_page(page("Four.", "Five."), engine=GOOGLE)
        self.assertEqual(len(google.requests), 1)
        self.assertEqual(second["failed_count"], 2)

    def test_no_connection_does_not_retry_paragraph_by_paragraph(self):
        google = self.use(lambda query, n: urllib.error.URLError("timed out"))
        result = PaperTranslator.translate_single_page(page("One.", "Two.", "Three."), engine=GOOGLE)
        self.assertEqual(len(google.requests), 1)
        self.assertEqual(result["failed_count"], 3)
        self.assertIn("연결하지 못했어요", result["failure_reason"])

    def test_a_trailing_newline_in_the_reply_still_splits_back(self):
        google = self.use(lambda query, n: gtx_reply("하나\n둘\n"))
        result = PaperTranslator.translate_single_page(page("One.", "Two."), engine=GOOGLE)
        self.assertEqual(len(google.requests), 1)
        self.assertEqual([p["ko"] for p in result["pairs"]], ["하나", "둘"])

    def test_rate_limit_waits_and_retries(self):
        google = self.use(lambda query, n: http_error(429) if n < 3 else gtx_reply("하나\n둘"))
        result = PaperTranslator.translate_single_page(page("One.", "Two."), engine=GOOGLE)
        self.assertEqual(len(google.requests), 3)
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [1, 2])
        self.assertEqual(result["failed_count"], 0)

    def test_rate_limit_on_every_try_counts_as_a_block(self):
        google = self.use(lambda query, n: http_error(429))
        result = PaperTranslator.translate_single_page(page("One.", "Two."), engine=GOOGLE)
        self.assertEqual(len(google.requests), 3)
        self.assertEqual(result["failed_count"], 2)
        self.assertGreater(rate_limit.google_blocked_until, 0)

    def test_a_block_outlives_a_reload_of_the_translator_module(self):
        self.use(lambda query, n: http_error(302))
        PaperTranslator.translate_single_page(page("One."), engine=GOOGLE)
        reloaded = importlib.reload(core.translator).PaperTranslator
        fake = FakeGoogle(lambda query, n: gtx_reply("번역"))
        with mock.patch.object(reloaded, "_google_opener", fake):
            result = reloaded.translate_single_page(page("Two."), engine=GOOGLE)
        self.assertEqual(fake.requests, [])
        self.assertEqual(result["failed_count"], 1)

    def test_long_pages_split_into_batches_within_the_size_limit(self):
        with mock.patch.object(PaperTranslator, "GOOGLE_BATCH_CHARS", 50):
            self.assertEqual(PaperTranslator._google_batches(["a" * 20, "b" * 20, "", "c" * 20]), [[0, 1], [3]])


def gemini_reply(translations):
    """A reply keyed by paragraph id; None leaves that id out."""
    keyed = {f"p{i + 1}": ko for i, ko in enumerate(translations) if ko is not None}
    body = {"candidates": [{"content": {"parts": [{"text": json.dumps(keyed, ensure_ascii=False)}]}}]}
    return io.BytesIO(json.dumps(body, ensure_ascii=False).encode("utf-8"))


class GeminiRequestTests(unittest.TestCase):
    def test_gemini_translates_with_low_thinking_and_one_required_key_per_paragraph(self):
        # Default thinking took 16-45 s a page and could spend the whole output limit before the answer.
        self.assertEqual(PaperTranslator.SUPPORTED_ENGINES, [GOOGLE, GEMINI])
        with mock.patch("core.translator.urllib.request.urlopen", return_value=gemini_reply(["첫", "둘"])) as urlopen:
            PaperTranslator.translate_single_page(page("First.", "Second."), engine=GEMINI, custom_api_key="k" * 20)
        request = urlopen.call_args.args[0]
        self.assertIn("gemini-3.8-flash", request.full_url)
        self.assertNotIn("k" * 20, request.full_url)
        config = json.loads(request.data)["generationConfig"]
        self.assertEqual(config["thinkingConfig"], {"thinkingLevel": "low"})
        self.assertEqual(config["responseSchema"]["required"], ["p1", "p2"])
        prompt = json.loads(request.data)["contents"][0]["parts"][0]["text"]
        self.assertIn('"p2": "Second."', prompt)

    def test_a_paragraph_left_out_does_not_shift_the_ones_after_it(self):
        # The model once skipped a formula line; answered by position, every later paragraph moved up by one.
        reply = gemini_reply(["첫 문단", None, "셋째 문단"])
        with mock.patch("core.translator.urllib.request.urlopen", return_value=reply):
            result = PaperTranslator.translate_single_page(page("First.", "x = y (1)", "Third."), engine=GEMINI,
                                                           custom_api_key="k" * 20)
        self.assertEqual([p["ko"] for p in result["pairs"]], ["첫 문단", "x = y (1)", "셋째 문단"])
        self.assertEqual(result["failed_count"], 1)
        self.assertTrue(result["pairs"][1]["untranslated"])

    def test_an_unsupported_thinking_level_moves_to_the_next_model(self):
        refused = urllib.error.HTTPError("https://gemini.example", 400, "bad", {},
                                         io.BytesIO(b"Thinking level MINIMAL is not supported for this model."))
        with mock.patch("core.translator.urllib.request.urlopen", side_effect=[refused, gemini_reply(["번역"])]) as urlopen:
            result = PaperTranslator.translate_single_page(page("Text."), engine=GEMINI, custom_api_key="k" * 20)
        self.assertEqual(urlopen.call_count, 2)
        self.assertFalse(result["is_fallback"])
        self.assertEqual(result["model_used"], "gemini-3.7-flash")

    def test_a_rejected_key_is_not_sent_to_every_model(self):
        rejected = urllib.error.HTTPError("https://gemini.example", 400, "bad", {}, io.BytesIO(b"API_KEY_INVALID"))
        with mock.patch("core.translator.urllib.request.urlopen", side_effect=rejected) as urlopen, \
                mock.patch.object(PaperTranslator, "_translate_with_google",
                                  return_value={"page_num": 1, "pairs": [{"id": 1, "en": "Text.", "ko": "텍스트", "bbox": BBOX}]}):
            result = PaperTranslator.translate_single_page(page("Text."), engine=GEMINI, custom_api_key="k" * 20)
        self.assertEqual(urlopen.call_count, 1)
        self.assertTrue(result["is_fallback"])
        self.assertIn("HTTP 400", result["fallback_reason"])

    def test_quota_moves_to_the_next_model(self):
        answers = [urllib.error.HTTPError("https://gemini.example", 429, "quota", {}, io.BytesIO(b"")), gemini_reply(["번역"])]
        with mock.patch("core.translator.urllib.request.urlopen", side_effect=answers) as urlopen:
            result = PaperTranslator.translate_single_page(page("Text."), engine=GEMINI, custom_api_key="k" * 20)
        self.assertEqual(urlopen.call_count, 2)
        fallback = urlopen.call_args.args[0]
        self.assertIn("gemini-3.7-flash", fallback.full_url)
        self.assertEqual(json.loads(fallback.data)["generationConfig"]["thinkingConfig"], {"thinkingLevel": "low"})
        self.assertEqual(result["model_used"], "gemini-3.7-flash")


if __name__ == "__main__":
    unittest.main()
