"""Jobsite Defense — shared structural protocols.

Phase 2.5 change
----------------
``Entity.update`` now takes a ``world: Any`` second argument so entities
can read and write shared game state (enemy list, economy, etc.) without
holding module-level references.  ``Any`` is used for the type annotation
to avoid a circular import between ``protocols.py`` and ``world.py``;
callers that need the concrete type import ``World`` directly from
``src.world``.

``Clickable`` is unchanged.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

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

    def update(self, dt: float, world: Any) -> None:  # noqa: ANN401
        """Advance the entity's state by *dt* seconds.

        Args:
            dt: Delta-time in seconds since the previous frame.
                Always clamped to ≤ 0.05 s by the game loop.
            world: Shared ``World`` context (typed ``Any`` to avoid
                circular imports; use ``isinstance`` or cast as needed).
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
