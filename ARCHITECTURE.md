# 🏛️ Jobsite Defense — System Architecture & Engineering Reference

> Comprehensive architectural design document for **Jobsite Defense**, detailing structural protocols, simulation subsystems, render pipelines, event buses, and data-flow invariants.

---

## 📋 Table of Contents

1. [High-Level Topology](#1-high-level-topology)
2. [Display Lifecycle & Variable Timestep Loop](#2-display-lifecycle--variable-timestep-loop)
3. [Scene Architecture & Stack Management](#3-scene-architecture--stack-management)
4. [World Context & Event Bus](#4-world-context--event-bus)
5. [Level Blueprints & Geometry Rasterization](#5-level-blueprints--geometry-rasterization)
6. [Combat Math, Prediction, & Homing Ballistics](#6-combat-math-prediction--homing-ballistics)
7. [Status Modifiers & Boss Aura Mechanics](#7-status-modifiers--boss-aura-mechanics)
8. [Contextual Radial UI & Clamping](#8-contextual-radial-ui--clamping)
9. [Meta-Progression & Atomic File Persistence](#9-meta-progression--atomic-file-persistence)
10. [Layer Ordering & Rendering Pipeline](#10-layer-ordering--rendering-pipeline)
11. [Performance Optimization Invariants](#11-performance-optimization-invariants)
12. [Testing Protocol & Quality Assurance](#12-testing-protocol--quality-assurance)

---

## 1. High-Level Topology

```
┌────────────────────────────────────────────────────────────────────────┐
│                              Application Entry                         │
│                                 (main.py)                              │
│         Pygame Init • Display Mode (SCALED + VSync) • Main Loop        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ owns
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                              SceneManager                              │
│                                (scene.py)                              │
│   Active Stack: [ TitleScene | LevelSelectScene | GameplayScene ]      │
│   Modal Overlays: [ PauseScene | TalentTreeScene ]                     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ delegates
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                             GameplayScene                              │
│  ├── Static Surface Cache (1 Blit Background Layer)                    │
│  ├── Dirty-Flag Entity Sorter (Optimized Layer Sorting)                │
│  ├── WaveManager (Entity Layer 5)                                      │
│  ├── RadialMenu (Entity Layer 90 & Clickable)                          │
│  └── World Context                                                     │
│      ├── LevelData (Paths, Road Frozenset, Powerup Map)                │
│      ├── Economy (Budget Dollars, Client Patience Lives)               │
│      ├── Towers (Spatial Grid Map: dict[tuple[int, int], Tower])       │
│      ├── Enemies (List of active Enemy entities)                       │
│      ├── Projectiles (List of active ballistic / homing entities)     │
│      ├── SaveData (Active talent perks: Union Dues, Heavy Ammo, etc.)  │
│      └── Event Bus (GameEvent structured queue)                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Display Lifecycle & Variable Timestep Loop

The application entry point in `src/main.py` establishes an SDL2 hardware window configured for high efficiency:

```python
screen = pygame.display.set_mode((960, 720), pygame.SCALED, vsync=1)
```

### Timestep Clamping
To prevent simulation instability ("bullet tunneling" or waypoint skipping) during OS frame hitching on dual-core hardware, delta time is clamped:

$$\Delta t = \min\left(\frac{\text{clock.tick}(60)}{1000.0}, 0.05\right)$$

- **Variable Step**: Ensures smooth visual interpolation regardless of minor framerate variance.
- **$\Delta t$ Cap**: Guarantees that lag spikes never advance an entity by more than 50 milliseconds in a single frame.
- **FPS Telemetry**: Frame rates are collected directly from `clock.get_fps()` and exposed to `SceneManager.fps` for HUD display.

---

## 3. Scene Architecture & Stack Management

Screen states are encapsulated using the structural `Scene` protocol (`src/scene.py`):

```python
@runtime_checkable
class Scene(Protocol):
    def handle_event(self, event: pygame.event.Event) -> bool: ...
    def update(self, dt: float) -> None: ...
    def draw(self, surface: pygame.Surface) -> None: ...
```

### Scene Stack Semantics (`SceneManager`)
- **`change(scene)`**: Clears the stack and replaces the active root scene (e.g. transitioning from `TitleScene` to `GameplayScene`).
- **`push(scene)`**: Pushes a modal overlay on top of the active scene (e.g. `PauseScene` or `TalentTreeScene`). The previous scene stops receiving updates and input, but remains rendered underneath transparent overlays.
- **`pop()`**: Removes the modal overlay and restores active focus to the previous scene.

### Implemented Scenes
1. **`TitleScene`**: Primary entry screen handling options to launch contracts, browse blueprint selection, enter the Union Hall, or exit.
2. **`LevelSelectScene`**: Blueprint browser for contracts (`level_1.json`, `level_2.json`) wrapped in safe `try/except LevelError` handlers.
3. **`GameplayScene`**: Active match simulation managing entities, HUD rendering, win/loss evaluation, and game-over / victory restarts.
4. **`PauseScene`**: Semi-transparent modal overlay freezing match simulation while listening for resume (`P`/`ESC`) or quit (`Q`) keys.
5. **`TalentTreeScene`**: Interactive meta-progression shop (`src/talent_ui.py`) displaying unlockable perks with automatic transaction rollback upon I/O faults.

---

## 4. World Context & Event Bus

The `World` dataclass (`src/world.py`) serves as the central dependency injected into every entity update cycle (`entity.update(dt, world)`).

### Event Bus Subsystem
To decouple combat logic from sound, particle rendering, and telemetry systems, `World` provides an integrated event bus:

```python
class GameEvent(Enum):
    SHOT    = auto()   # Fired when any tower launches an attack
    KILL    = auto()   # Fired when an enemy health drops to <= 0
    LEAK    = auto()   # Fired when an enemy exits via final waypoint
    BUILD   = auto()   # Fired on successful tower placement
    SELL    = auto()   # Fired on tower liquidation
    UPGRADE = auto()   # Fired on tower tier advancement
    STUN    = auto()   # Fired when a target is incapacitated
    SPLASH  = auto()   # Fired when a concrete glob detonates
```

- **`world.emit(kind, pos, **data)`**: Appends an `Event(kind, pos, data)` to the queue.
- **`world.drain_events()`**: Empties and returns all events accumulated during the frame. Called by `GameplayScene.update()` after the entity update and cull pass.

---

## 5. Level Blueprints & Geometry Rasterization

Levels are stored as declarative JSON documents in `levels/`. The level loader (`src/level.py`) parses, validates, and freezes geometry into an immutable `LevelData` structure:

### Strict Validation Rules
1. **Path Continuity**: Every defined route must contain at least 2 coordinate points.
2. **Orthogonal Segments**: Ground roads must connect strictly via axis-aligned segments; diagonal segments raise immediate `ValueError`.
3. **Coordinate Clamping**: All rasterized road cells are filtered strictly between $[0, \text{GRID\_COLS})$ and $[0, \text{GRID\_ROWS})$.
4. **Power-up Separation**: Power-up coordinates cannot overlap any road cell ($\text{powerups} \cap \text{road} = \emptyset$).
5. **Wave Archetype Integrity**: All wave definitions must reference valid registered enemy classes and existing path identifiers.

### Multi-Route Topologies
`LevelData.paths` maps route identifiers to `PathData`:
- `level_1.json`: Features single primary path `main`.
- `level_2.json`: Features dual paths `main` and `flank`, enabling concurrent approach vectors.
- Waypoint coordinates are stored as immutable primitive tuples `tuple[tuple[float, float], ...]` to prevent accidental shared-state mutation across enemy instances.

---

## 6. Combat Math, Prediction, & Homing Ballistics

### 1. Hit-Scan Direct Combat (`NailGunner`)
Instantaneous line-of-sight targeting. Evaluates enemies in range, deducts damage immediately, and displays a temporary high-visibility yellow shot beam (`_shot_flash`).

### 2. Predictive Intercept Solver (`ConcretePump`)
Ballistic artillery firing slow-moving globs ($v = 250\text{ px/s}$) requires predictive target leading. The tower executes a 3-pass iterative lead calculation:

$$\Delta t_{0} = \frac{\|\mathbf{p}_{\text{target}} - \mathbf{p}_{\text{tower}}\|}{v_{\text{glob}}}$$

$$\mathbf{p}_{\text{aim}}^{(k+1)} = \text{target.predict\_pos}\left(\frac{\|\mathbf{p}_{\text{aim}}^{(k)} - \mathbf{p}_{\text{tower}}\|}{v_{\text{glob}}}\right)$$

Inside `Enemy.predict_pos(seconds)`:
The enemy simulates its trajectory forward along its discrete waypoint segments, computing an exact travel budget that accurately models expiring speed debuffs and active stun locks.

### 3. Homing Ballistics & Retargeting (`TarpProjectile`)
`TarpCannon` launches high-speed homing net missiles ($v = 400\text{ px/s}$) that continuously steer towards `target.pos`.
- **Anti-Air Prioritization**: Automatically prioritizes flying units (`RainCloud`) over closer ground creeps.
- **Dynamic Retargeting**: If the original target is destroyed by another tower while the projectile is in mid-air, the projectile calls `_retarget(world)`, scanning for the closest living enemy to prevent wasted ammunition.

---

## 7. Status Modifiers & Boss Aura Mechanics

### Status Modifiers (`src/enemy.py`)
Status debuffs are managed in `enemy.modifiers`:
- **`SpeedModifier(multiplier, duration)`**:
  - Overwriting rule: Weaker debuffs (higher multiplier) are ignored. Stronger debuffs overwrite current speed factor. Equal multipliers take $\max(\text{current.dur}, \text{new.dur})$.
- **`StunModifier(duration)`**:
  - Sets velocity to $0\text{ px/s}$.
  - **Diminishing Returns Lockout**: Non-bosses receive post-stun lockout of $\text{duration} + 1.5\text{s}$. Bosses receive $\text{duration} + 3.0\text{s}$. Creeps are immune to subsequent stuns until this lockout timer expires.

### Stop-Work Order Aura (`OshaInspector`)
The OSHA Inspector radiates an active aura with a radius of $150\text{ px}$ ($2.5\text{ cells}$):
1. Prior to each frame update, `world.refresh_auras()` resets all towers to `is_disabled = False`.
2. Each live enemy executes `apply_aura(world)`.
3. If an `OshaInspector` is alive and **not stunned**, it disables every tower within range.
4. Disabled towers skip their cooldown ticking, cease targeting, and render a prominent red cross overlay.

---

## 8. Contextual Radial UI & Clamping

The Radial Build Menu (`src/ui.py`) satisfies `Entity` (Layer 90) and `Clickable`.

### 8-Angle Orbit & Safe Clamping
Menu buttons orbit the clicked cell center at $R_{\text{orbit}} = 80\text{ px}$ across preferred angles $(90^\circ, 270^\circ, 0^\circ, 180^\circ, 45^\circ, 135^\circ, 225^\circ, 315^\circ)$.
To prevent button centers from clipping outside the viewport on edge cells (such as row 0 or row 11), coordinates are clamped:

$$x_{\text{clamped}} = \operatorname{clamp}(x_{\text{raw}}, R_{\text{button}}, W - R_{\text{button}})$$

$$y_{\text{clamped}} = \operatorname{clamp}(y_{\text{raw}}, R_{\text{button}}, H - R_{\text{button}})$$

### Dynamic Registry & Max Tier States
- Empty cells pull buildable options dynamically from `src.tower.BUILDABLE`.
- Occupied cells present a liquidation button ("Sell", refunding $70\%$) and the next upgrade tier.
- Once a tower reaches its final upgrade tier, the upgrade button transforms into a disabled "Max Tier" indicator (`enabled = False`). Clicking this button consumes the event without raising errors or altering player budget.

---

## 9. Meta-Progression & Atomic File Persistence

Persistent player progress (`SaveData` in `src/save.py`) records spendable Union Equity and unlocked perk IDs.

### Platform User Data Paths
To follow OS standards and avoid permissions issues:
- **Windows**: `%APPDATA%\JobsiteDefense\save_data.json`
- **POSIX**: `~/.local/share/JobsiteDefense/save_data.json`

### Atomic Persistence Pipeline
1. Payload is serialized to a `.tmp` file alongside the target.
2. File buffers are explicitly flushed via `f.flush()` and committed to disk with `os.fsync(f.fileno())`.
3. Atomic replacement is executed via `os.replace(tmp_target, target)`.
4. **Windows File-Locking Backoff**: If an external process (antivirus or indexer) momentarily locks the file producing `PermissionError`, the save engine retries up to 5 times with exponential backoff before raising.
5. **UI State Rollback**: In `TalentTreeScene`, equity and perks are snapshotted prior to debiting; if an I/O fault occurs during save, the in-memory state is automatically restored.

---

## 10. Layer Ordering & Rendering Pipeline

Entities are rendered strictly according to the painter's algorithm governed by the `layer: int` attribute on each `Entity`:

| Layer | Subsystem / Component | Description |
|---|---|---|
| **0** | **Static Layer** | Background grass, roads, power-up labels, and grid lines (pre-baked surface) |
| **5** | **`WaveManager`** | HUD wave counter and countdown timers |
| **10** | **`Enemy`** | Rotted 2×4s, HOA members, Rain Clouds, OSHA Inspector boss |
| **20** | **`Tower`** | Placed towers, rotating turrets, selection highlights, range circles |
| **30** | **`Projectile`** | Flying Concrete Globs and homing Tarp Projectiles |
| **90** | **`RadialMenu`** | Interactive contextual build and upgrade buttons |
| **100** | **HUD & Overlays** | Budget, patience counter, live FPS readout, modal banners |

---

## 11. Performance Optimization Invariants

Engineered to sustain a locked **60 FPS** on the baseline **Intel HD Graphics 620** integrated GPU:

1. **Pre-baked Static Surface (`src/render.py`)**:
   - The entire background grid, asphalt roads, colored power-up cells, and text badges are rendered once to an offscreen surface at level load and converted with `.convert()`.
   - Replaces 75+ individual CPU draw calls per frame with a single hardware DMA blit.
2. **Dirty-Flag Entity Sorter (`src/scene.py`)**:
   - `GameplayScene._build_entity_list()` maintains a `self._dirty: bool` flag.
   - Entity list concatenation and sorting only occur when entities are spawned, destroyed, built, or liquidated. Static frames and event polls reuse the cached list.
3. **Squared Distance Checks**:
   - Range rings, splash radii, and nearest-enemy searches evaluate distance squared (`dist_sq <= range_sq`), eliminating square root calculations in inner combat loops.
4. **Sparse Spatial Collections**:
   - Grid occupancy is tracked with `dict[tuple[int, int], Tower]` and `frozenset[tuple[int, int]]`, avoiding dense 2D matrix allocations.

---

## 12. Testing Protocol & Quality Assurance

The codebase enforces strict continuous testing:

- **138 Automated Tests** across 10 test suites covering 100% of core simulation logic.
- **Headless Pytest Fixture (`tests/conftest.py`)**: Globally sets `SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy`, allowing complete headless execution in CI environments.
- **Strict Typing Gate**: `mypy --strict src/ tests/` (0 errors permitted).
- **Fast Linting Gate**: `ruff check src/ tests/` with import sorting and annotations enforced.
