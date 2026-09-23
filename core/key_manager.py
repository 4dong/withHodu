"""
API Key Storage & Slot Manager (.env & Multi-Slot Disk Sync)
Manages persistent API key slots, default selections, .env synchronization, and key masking.
"""

import os
import json
import uuid
import re
from typing import Dict, Any, List, Optional, Tuple

DEFAULT_KEY_STORE_PATH = os.path.expanduser("~/.gemini_paper_keys.json")


def _make_private(path: str) -> None:
    """Key files are readable by their owner only; files written before this rule are tightened on use."""
    try:
        if os.path.exists(path) and os.stat(path).st_mode & 0o077:
            os.chmod(path, 0o600)
    except OSError:
        pass


def _write_private(path: str, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    _make_private(path)

class KeyManager:
    """Manages multi-slot Gemini API keys persistently across local disk and .env files."""

    _custom_store_path: Optional[str] = None

    @classmethod
    def get_store_path(cls) -> str:
        return cls._custom_store_path or DEFAULT_KEY_STORE_PATH

    @classmethod
    def set_custom_store_path(cls, path: Optional[str]):
        """Used for isolated testing without affecting user's real key store."""
        cls._custom_store_path = path

    @classmethod
    def _find_env_file_path(cls) -> Optional[str]:
        """Finds .env file in current working directory or project root."""
        candidates = [
            os.path.join(os.getcwd(), ".env"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
            os.path.expanduser("~/Anti-paper/.env")
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

    @classmethod
    def _load_env_key(cls) -> Optional[str]:
        """Reads GEMINI_API_KEY directly from .env file or system environment."""
        # 1. Check system environment
        if os.environ.get("GEMINI_API_KEY"):
            return os.environ["GEMINI_API_KEY"].strip()

        # 2. Check .env file
        env_path = cls._find_env_file_path()
        if env_path and os.path.exists(env_path):
            _make_private(env_path)
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                os.environ["GEMINI_API_KEY"] = val
                                return val
            except Exception as e:
                print(f"Error reading .env: {e}")

        return None

    @classmethod
    def _sync_to_env_file(cls, api_key: str):
        """Saves or updates GEMINI_API_KEY inside .env file persistently."""
        if not api_key:
            return

        env_path = cls._find_env_file_path()
        if not env_path:
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

        try:
            lines = []
            key_found = False
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

            new_lines = []
            for line in lines:
                if line.strip().startswith("GEMINI_API_KEY="):
                    new_lines.append(f"GEMINI_API_KEY={api_key.strip()}\n")
                    key_found = True
                else:
                    new_lines.append(line)

            if not key_found:
                if new_lines and not new_lines[-1].endswith("\n"):
                    new_lines.append("\n")
                new_lines.append(f"GEMINI_API_KEY={api_key.strip()}\n")

            _write_private(env_path, "".join(new_lines))

            # Update live runtime environment
            os.environ["GEMINI_API_KEY"] = api_key.strip()
        except Exception as e:
            print(f"Error writing .env file: {e}")

    @classmethod
    def _load_data(cls) -> Dict[str, Any]:
        store_path = cls.get_store_path()
        env_key = cls._load_env_key()

        if not os.path.exists(store_path):
            initial_data = {
                "default_slot_id": "slot_env" if env_key else None,
                "slots": {}
            }
            if env_key:
                initial_data["slots"]["slot_env"] = {
                    "id": "slot_env",
                    "name": ".env 자동 로드 키",
                    "key": env_key,
                    "is_default": True
                }
            cls._save_data(initial_data)
            return initial_data

        _make_private(store_path)
        try:
            with open(store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading key store: {e}")
            data = {"default_slot_id": None, "slots": {}}

        # If .env has a key but not registered in slots, auto-import it
        if env_key:
            has_env_slot = any(s.get("key") == env_key for s in data.get("slots", {}).values())
            if not has_env_slot:
                data.setdefault("slots", {})["slot_env"] = {
                    "id": "slot_env",
                    "name": ".env 자동 로드 키",
                    "key": env_key,
                    "is_default": not bool(data.get("default_slot_id"))
                }
                if not data.get("default_slot_id"):
                    data["default_slot_id"] = "slot_env"
                cls._save_data(data)

        return data

    @classmethod
    def _save_data(cls, data: Dict[str, Any]):
        store_path = cls.get_store_path()
        try:
            parent_dir = os.path.dirname(store_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            _write_private(store_path, json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Error saving key store: {e}")

    @classmethod
    def get_all_slots(cls) -> List[Dict[str, Any]]:
        """Returns list of all saved key slots."""
        data = cls._load_data()
        return list(data.get("slots", {}).values())

    @classmethod
    def get_active_key(cls, selected_slot_id: Optional[str] = None) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Returns (api_key, slot_info).
        If selected_slot_id is provided, returns that slot; otherwise returns default slot or .env fallback.
        """
        data = cls._load_data()
        slots = data.get("slots", {})
        
        # 1. Explicit slot requested
        if selected_slot_id and selected_slot_id in slots:
            slot = slots[selected_slot_id]
            return slot.get("key"), slot

        # 2. Use default slot
        def_id = data.get("default_slot_id")
        if def_id and def_id in slots:
            slot = slots[def_id]
            return slot.get("key"), slot

        # 3. If any slot exists, use the first one
        if slots:
            first_slot = next(iter(slots.values()))
            return first_slot.get("key"), first_slot

        # 4. Fallback to .env / os.environ
        env_key = cls._load_env_key()
        if env_key:
            return env_key, {"id": "env", "name": ".env 환경변수", "key": env_key, "is_default": True}

        return None, None

    @classmethod
    def get_api_key(cls, provider: str = "gemini") -> Optional[str]:
        """Convenience method returning the active API key string or None."""
        key, _ = cls.get_active_key()
        return key

    @classmethod
    def save_slot(cls, name: str, api_key: str, set_as_default: bool = False, sync_env: bool = True) -> str:
        """Adds or updates a key slot, saves to JSON store, and syncs to .env."""
        data = cls._load_data()
        slot_id = f"slot_{uuid.uuid4().hex[:8]}"
        clean_key = api_key.strip()
        clean_name = name.strip() or "내 Gemini 키"

        if set_as_default:
            for s in data.get("slots", {}).values():
                s["is_default"] = False
            data["default_slot_id"] = slot_id

        data.setdefault("slots", {})[slot_id] = {
            "id": slot_id,
            "name": clean_name,
            "key": clean_key,
            "is_default": set_as_default or (len(data["slots"]) == 0)
        }

        if len(data["slots"]) == 1 or set_as_default:
            data["default_slot_id"] = slot_id

        cls._save_data(data)

        # Sync to .env file so it never gets lost
        if sync_env and (set_as_default or len(data["slots"]) == 1):
            cls._sync_to_env_file(clean_key)

        return slot_id

    @classmethod
    def set_default(cls, slot_id: str, sync_env: bool = True):
        """Sets a specific slot as default and updates .env."""
        data = cls._load_data()
        slots = data.get("slots", {})
        if slot_id in slots:
            for sid, s in slots.items():
                s["is_default"] = (sid == slot_id)
            data["default_slot_id"] = slot_id
            cls._save_data(data)

            if sync_env:
                def_key = slots[slot_id].get("key")
                if def_key:
                    cls._sync_to_env_file(def_key)

    @classmethod
    def delete_slot(cls, slot_id: str):
        """Deletes a key slot."""
        data = cls._load_data()
        slots = data.get("slots", {})
        if slot_id in slots:
            del slots[slot_id]
            if data.get("default_slot_id") == slot_id:
                data["default_slot_id"] = next(iter(slots.keys())) if slots else None
                if data["default_slot_id"]:
                    slots[data["default_slot_id"]]["is_default"] = True
                    cls._sync_to_env_file(slots[data["default_slot_id"]]["key"])
            cls._save_data(data)

    @staticmethod
    def mask_key(key: Optional[str]) -> str:
        """Masks key for safe UI display (e.g. AIzaSy...9aBc)."""
        if not key or len(key) < 10:
            return "미설정"
        return f"{key[:6]}...{key[-4:]}"
