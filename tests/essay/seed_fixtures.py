"""Loads private seed/evaluation fixtures, skipping tests when they are not configured."""

import json
import unittest

from core.essay.seed import SEED_DIR_ENV, seed_data_file


def load_seed_json(name: str):
    path = seed_data_file(name)
    if path is None:
        raise unittest.SkipTest(f"{name} not found: set {SEED_DIR_ENV} to the private handoff folder to run this test")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
