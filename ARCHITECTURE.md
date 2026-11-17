# 🏛️ Jobsite Defense — System Architecture

> This document describes the core data model, game-loop structure, and
> module responsibilities for the **Jobsite Defense** tower-defense game.

---

## Table of Contents

- [High-Level Overview](#high-level-overview)
- [Game Loop](#game-loop)
- [Data Model](#data-model)
  - [Grid & Coordinate System](#grid--coordinate-system)
  - [Road](#road)
  - [Towers](#towers)
  - [Power-Up Tiles](#power-up-tiles)
  - [Enemies](#enemies)
  - [Waypoints & Pathing](#waypoints--pathing)
- [Module Map](#module-map)
- [Rendering Pipeline](#rendering-pipeline)
- [Performance Notes](#performance-notes)

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────┐
│                    Game Window                      │
│  ┌───────────────────────────────────────────────┐  │
│  │                   Grid                        │  │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   │  │
│  │  │     │ │ROAD │ │     │ │ROAD │ │     │   │  │
│  │  │     │ │░░░░░│ │     │ │░░░░░│ │     │   │  │
│  │  ├─────┤ ├─────┤ ├─────┤ ├─────┤ ├─────┤   │  │
│  │  │TOWER│ │ROAD │ │POWER│ │ROAD │ │     │   │  │
│  │  │  ⌂  │ │░░░░░│ │ 🧊  │ │░░░░░│ │     │   │  │
│  │  ├─────┤ ├─────┤ ├─────┤ ├─────┤ ├─────┤   │  │
│  │  │     │ │ROAD │ │ROAD │ │ROAD │ │     │   │  │
│  │  │     │ │░░░░░│ │░░░░░│ │░░░░░│ │     │   │  │
│  │  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘   │  │
│  │                                               │  │
│  │        ● Enemy (moving along road)            │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## Game Loop

The game uses a **variable time-step** loop running at a target of
**60 FPS**.

```
┌──────────────────────────────────────────────┐
│                 GAME LOOP                    │
│                                              │
│  1. dt = clock.tick(60) / 1000.0             │
│  2. Handle events (quit, input)              │
│  3. Update entities (enemy.move_towards)     │
│  4. Render frame                             │
│     a. Clear screen                          │
│     b. Draw grid lines                       │
│     c. Fill road cells (grey)                │
│     d. Fill power-up cells (colored)         │
│     e. Draw towers (future)                  │
│     f. Draw enemies                          │
│     g. Draw UI overlay (future)              │
│  5. pygame.display.flip()                    │
│  6. Loop → step 1                            │
└──────────────────────────────────────────────┘
```

**Why variable time-step?**  On the target hardware (integrated Intel HD
620), frame times may occasionally spike.  Multiplying velocities by `dt`
keeps movement smooth regardless of frame drops.

---

## Data Model

### Design Philosophy

> **Sparse over dense.**  We avoid allocating a full `rows × cols` 2D
> array.  Instead, only *occupied* cells are stored in sets or
> dictionaries.  Unlisted cells are implicitly "grass" (buildable ground).

### Grid & Coordinate System

| Property | Value |
|---|---|
| Cell size | 60 × 60 px |
| Grid dimensions | 16 columns × 12 rows |
| Window size | 960 × 720 px |
| Origin | Top-left corner `(0, 0)` |
| Coordinate order | `(col, row)` — column-first, matching `(x, y)` |

A cell's **pixel center** is computed as:

```
pixel_x = col * CELL_SIZE + CELL_SIZE // 2
pixel_y = row * CELL_SIZE + CELL_SIZE // 2
```

### Road

```python
ROAD_CELLS: frozenset[tuple[int, int]]
```

An **immutable set** of `(col, row)` tuples defining which cells are
road.  Enemies walk on road cells.  Towers **cannot** be placed on road.

**Why `frozenset`?**  The road layout is static per level.  Using a
frozenset prevents accidental mutation and enables O(1) membership tests
(`if (col, row) in ROAD_CELLS`).

### Towers

```python
towers: dict[tuple[int, int], TowerData]
```

A **dictionary** mapping `(col, row)` → tower data.  In Phase 1 this is
unused; in Phase 2+ it will hold dataclass instances:

```python
@dataclass
class TowerData:
    kind: str          # "nail_gunner", "concrete_pump", etc.
    level: int = 1
    cooldown: float = 0.0
```

### Power-Up Tiles

```python
powerup_tiles: dict[tuple[int, int], tuple[str, float]]
```

A **dictionary** mapping `(col, row)` → `(effect_name, multiplier)`.

Example:
```python
{
    (3, 2): ("attack_speed", 1.25),   # Yeti Cooler
    (10, 7): ("damage", 1.5),         # Heavy Air Compressor
    (7, 4): ("range", 1.25),          # Extension Cord
}
```

Towers placed adjacent to a power-up tile receive its buff.

### Enemies

Each enemy tracks its position as a **`pygame.Vector2`** (sub-pixel
precision) and its current **waypoint index**.

```python
@dataclass
class Enemy:
    pos: pygame.Vector2
    waypoint_index: int = 0
    speed: float = 120.0        # pixels per second
    health: float = 100.0       # (future)
```

Movement uses **`Vector2.move_towards(target, max_distance)`** each
frame, where `max_distance = speed * dt`.

### Waypoints & Pathing

```python
WAYPOINTS: tuple[tuple[int, int], ...]
```

An **ordered tuple** of `(col, row)` grid coordinates defining the
enemy path.  Enemies spawn at `WAYPOINTS[0]` and walk sequentially to
each subsequent waypoint.  When the final waypoint is reached, the enemy
either despawns or the player loses a life (Phase 3+).

Waypoints are converted to pixel centers for movement:

```python
target_px = pygame.Vector2(
    wp_col * CELL_SIZE + CELL_SIZE // 2,
    wp_row * CELL_SIZE + CELL_SIZE // 2,
)
```

---

## Module Map

```
src/
├── __init__.py      # Package marker
├── main.py          # Entry point: init, game loop, shutdown
├── settings.py      # All constants (colors, sizes, layout data)
├── grid.py          # draw_grid(), draw_cell_fill()
├── road.py          # ROAD_CELLS frozenset, draw_road()
├── enemy.py         # Enemy dataclass, update & draw logic
└── powerup.py       # powerup_tiles dict, draw_powerups()
```

| Module | Responsibility |
|---|---|
| `main.py` | Pygame init, window creation, owns the game loop, delegates to other modules |
| `settings.py` | Single source of truth for all tunable constants |
| `grid.py` | Draws the grid overlay and can highlight individual cells |
| `road.py` | Owns the road data and renders filled road cells |
| `enemy.py` | Enemy state, waypoint-following movement, circle rendering |
| `powerup.py` | Power-up tile data and colored cell rendering |

---

## Rendering Pipeline

Each frame is drawn in **painter's order** (back to front):

1. **Background fill** — dark green ("grass")
2. **Road cells** — asphalt grey rectangles
3. **Power-up cells** — semi-transparent colored overlays
4. **Grid lines** — thin dark lines for visual structure
5. **Enemies** — colored circles at their `Vector2` positions
6. *(Future)* **Towers** — sprites or geometric shapes on their cells
7. *(Future)* **Projectiles** — lines or small shapes
8. *(Future)* **UI overlay** — HUD, wave counter, currency

---

## Performance Notes

- **Target**: 60 FPS on Intel HD Graphics 620.
- **Software rendering** via SDL2 is sufficient for geometric shapes at
  960 × 720.  No GPU shaders are needed.
- **Sparse data** (frozenset, dict) keeps per-frame iteration to only
  the cells that matter, not all 192 cells.
- **`Vector2.move_towards()`** is a C-level Pygame-CE function —
  significantly faster than manual Python math.
- Future sprite rendering should use **`convert_alpha()`** on load and
  **dirty-rect updating** if full-screen redraws become a bottleneck.
