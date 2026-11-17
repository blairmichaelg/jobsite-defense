"""Jobsite Defense — shared structural protocols.

Defines the two core protocols used throughout the game:

``Entity``
    Every active game object (enemy, tower, projectile, boss).  Objects
    are stored in a single ``list[Entity]`` sorted by ``layer`` and
    iterated uniformly each frame.

``Clickable``
    Optional mixin for objects that consume mouse / keyboard events (e.g.
    the radial build menu, future tower-info panels).  ``handle_event``
    returns ``True`` when the event is consumed and should not propagate.

Both protocols are ``@runtime_checkable`` so ``isinstance`` can gate
debug tooling and test assertions without inheritance overhead.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pygame


@runtime_checkable
class Entity(Protocol):
    """Structural protocol shared by all active game objects.

    Attributes:
        layer: Render / update order.  Lower values are updated and drawn
               first.  Standard assignments:

               * 0  — background decorations (future)
               * 10 — enemies
               * 20 — towers
               * 30 — projectiles (future)
               * 90 — UI overlays (radial menu, HUD widgets)
    """

    layer: int

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


@runtime_checkable
class Clickable(Protocol):
    """Protocol for entities that consume pygame input events.

    Implementors inspect the event and return ``True`` if they handled it
    (preventing further propagation) or ``False`` to pass it along.
    """

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Process a single pygame event.

        Args:
            event: The raw pygame event (MOUSEBUTTONDOWN, KEYDOWN, etc.).

        Returns:
            ``True`` if the event was consumed; ``False`` to propagate.
        """
        ...
