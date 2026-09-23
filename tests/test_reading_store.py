"""Reading record: tiered translation reuse, no downgrade, last page read."""
import json
import os

from core.reading_store import ReadingStore, engine_tier, latest_read, result_tier

GOOGLE = "⚡️ Google Neural (무료 · 무제한)"
G35 = "🤖 Google Gemini 3.5 Flash (고성능 학술 AI · API 키 필요)"
G37 = "🤖 Google Gemini 3.7 Flash (최신 고성능 학술 AI · API 키 필요)"


def page(model=None, text="번역", fallback=False, failed=0):
    result = {"pairs": [{"en": "x", "ko": text}], "failed_count": failed, "is_fallback": fallback}
    if model:
        result["model_used"] = model
    return result


def test_tiers_follow_the_model_that_translated():
    assert engine_tier(GOOGLE) == 0 and engine_tier(G35) == 3.5 and engine_tier(G37) == 3.7
    assert result_tier(page()) == 0
    assert result_tier(page("gemini-3.7-flash")) == 3.7
    # Gemini 3.7 requested but the key only reached 2.5, or it fell back to Google
    assert result_tier(page("gemini-2.5-flash")) == 2.5
    assert result_tier(page("gemini-3.7-flash", fallback=True)) == 0


def test_higher_tier_serves_lower_engines_without_translation(tmp_path):
    store = ReadingStore(str(tmp_path))
    assert store.save_page(3, page("gemini-3.7-flash", "3.7 번역"), "prompt")
    for engine in (GOOGLE, G35, G37):
        hit = store.load_page(3, engine, "prompt")
        assert hit["pairs"][0]["ko"] == "3.7 번역" and hit["from_store"]


def test_lower_tier_is_not_enough_for_a_higher_engine(tmp_path):
    store = ReadingStore(str(tmp_path))
    store.save_page(1, page(), None)
    assert store.load_page(1, GOOGLE) is not None
    assert store.load_page(1, G35) is None


def test_upgrade_allowed_downgrade_refused(tmp_path):
    store = ReadingStore(str(tmp_path))
    assert store.save_page(1, page(text="google"))
    assert store.save_page(1, page("gemini-3.5-flash", "3.5"), "p")
    assert store.save_page(1, page("gemini-3.7-flash", "3.7"), "p")
    assert not store.save_page(1, page("gemini-3.5-flash", "3.5 again"), "p")
    assert not store.save_page(1, page(text="google again"))
    assert store.load_page(1, GOOGLE)["pairs"][0]["ko"] == "3.7"


def test_same_tier_overwrites_and_prompt_matters_at_equal_tier(tmp_path):
    store = ReadingStore(str(tmp_path))
    store.save_page(1, page("gemini-3.5-flash", "old"), "prompt A")
    assert store.load_page(1, G35, "prompt B") is None  # changed prompt: translate again
    assert store.save_page(1, page("gemini-3.5-flash", "new"), "prompt B")
    assert store.load_page(1, G35, "prompt B")["pairs"][0]["ko"] == "new"
    assert store.load_page(1, GOOGLE, "anything")["pairs"][0]["ko"] == "new"


def test_incomplete_pages_and_old_layouts_are_not_reused(tmp_path):
    store = ReadingStore(str(tmp_path))
    assert not store.save_page(1, page(failed=2))
    assert store.load_page(1, GOOGLE) is None
    ReadingStore(str(tmp_path), layout_version="old").save_page(2, page())
    assert store.load_page(2, GOOGLE) is None
    assert store.translated_pages() == {}


def test_stored_marker_is_not_written_back(tmp_path):
    store = ReadingStore(str(tmp_path))
    store.save_page(1, page())
    store.save_page(1, store.load_page(1, GOOGLE))
    with open(os.path.join(tmp_path, "translations", "page_1.json"), encoding="utf-8") as f:
        assert "from_store" not in json.load(f)["result"]


def test_progress_and_latest_read(tmp_path):
    root = tmp_path / "archive"
    older, newer = root / "TTS" / "2024_A", root / "default" / "2025_B"
    for folder in (older, newer):
        folder.mkdir(parents=True)
        (folder / "metadata.json").write_text("{}", encoding="utf-8")
    ReadingStore(str(older)).record_page(4, 10)
    ReadingStore(str(newer)).record_page(7, 22)
    assert ReadingStore(str(newer)).progress()["last_page"] == 7
    latest = latest_read(str(root))
    assert latest["paper_dir"] == str(newer) and latest["last_page"] == 7 and latest["total_pages"] == 22
    assert ReadingStore(str(newer)).translated_pages() == {}
