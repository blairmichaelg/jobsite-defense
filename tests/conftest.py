"""Pytest configuration — session-scoped fixtures shared across all test modules.

Sets the SDL ``dummy`` video and audio drivers **before** any test module
imports pygame, ensuring headless operation in CI and during local
``pytest`` runs without a display.  Doing this in ``conftest.py`` means
individual test files no longer need ``os.environ`` boilerplate.
"""

from __future__ import annotations

import os

import pygame
import pytest

# Must be set before the first pygame.init() anywhere in the session.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


@pytest.fixture(scope="session", autouse=True)
def _pygame_session() -> None:
    """Initialise pygame once for the whole test session and quit after."""
    pygame.init()
    yield  # type: ignore[misc]
    pygame.quit()
