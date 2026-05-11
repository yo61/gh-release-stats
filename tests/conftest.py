"""Shared pytest fixtures for gh-release-stats tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture() -> Callable[[str], Any]:
    """Return a function that loads a named JSON fixture."""

    def _load(name: str) -> Any:
        return json.loads((FIXTURES_DIR / name).read_text())

    return _load
