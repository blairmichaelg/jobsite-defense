"""Jobsite Defense — shared structural protocols.

Defines the ``Entity`` protocol that all game objects (enemies, towers,
projectiles, bosses) must satisfy.  Using a ``Protocol`` rather than an
abstract base class keeps the coupling loose: any class with the right
method signatures qualifies automatically, without inheritance.

Usage::

    from src.protocols import Entity

    entities: list[Entity] = [enemy, tower, projectile]
    for ent in entities:
        ent.update(dt)
        ent.draw(screen)
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pygame


@runtime_checkable
class Entity(Protocol):
    """Structural protocol shared by all active game objects.

    Any class that exposes ``update`` and ``draw`` with the correct
    signatures is considered an ``Entity`` — no explicit inheritance
    required.

    ``@runtime_checkable`` allows ``isinstance(obj, Entity)`` checks,
    which is useful for debug tooling and test assertions.
    """

    def update(self, dt: float) -> None:
        """Advance the entity's state by *dt* seconds.

        Args:
            dt: Delta-time in seconds since the previous frame.
                Always clamped to ≤ 0.05 s by the game loop.
        """
        ...

    def draw(self, surface: pygame.Surface) -> None:
        """Render the entity onto *surface*.

        Args:
            surface: The main display surface (or any target surface).
        """
        ...
