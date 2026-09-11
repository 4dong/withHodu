"""
Unit Test for KeyManager Multi-Slot API Key Storage and Selection (Isolated Test Mode)
"""

import os
import sys
import tempfile

# Ensure root directory in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.key_manager import KeyManager

def test_key_manager_lifecycle():
    # Use isolated temporary test store path to protect user's real keys
    temp_dir = tempfile.mkdtemp()
    temp_store_path = os.path.join(temp_dir, "test_keys.json")
    KeyManager.set_custom_store_path(temp_store_path)

    try:
        # 1. Slot Creation & Persistence
        slot1_id = KeyManager.save_slot("테스트 Gemini Flash 키", "AIzaSyFakeKey1234567890Flash", set_as_default=True, sync_env=False)
        slot2_id = KeyManager.save_slot("테스트 Pro 키", "AIzaSyFakeKey9876543210Pro", set_as_default=False, sync_env=False)

        all_slots = KeyManager.get_all_slots()
        assert len(all_slots) >= 2, "Failed to save key slots"

        # 2. Default Key Resolution
        active_key, active_slot = KeyManager.get_active_key()
        assert "Flash" in active_key
        assert active_slot["is_default"] is True

        # 3. Default Switching
        KeyManager.set_default(slot2_id, sync_env=False)
        active_key2, active_slot2 = KeyManager.get_active_key()
        assert "Pro" in active_key2
        assert active_slot2["is_default"] is True

        # 4. Slot Selection by ID
        key_sel, slot_sel = KeyManager.get_active_key(slot1_id)
        assert "Flash" in key_sel
        assert slot_sel["id"] == slot1_id

        # 5. Slot Deletion
        KeyManager.delete_slot(slot1_id)
        remaining_slots = KeyManager.get_all_slots()
        assert not any(s["id"] == slot1_id for s in remaining_slots)

    finally:
        # Reset back to default path and cleanup temp test file
        KeyManager.set_custom_store_path(None)
        if os.path.exists(temp_store_path):
            os.remove(temp_store_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)

if __name__ == "__main__":
    test_key_manager_lifecycle()
    print("✅ KeyManager tests passed.")
