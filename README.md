# 🏗️ Jobsite Defense

**A 2D Tower Defense game where the commercial framing jobsite fights back.**

Defend the project site against waves of rotten lumber, overzealous HOA inspectors, and rain delays. Place heavy machinery tool-towers, tap into jobsite power-up tiles, manage project budgets and client patience, unlock persistent union perks, and survive the OSHA Stop-Work Order.

> *"If the building don't get 'em, the nail gun will."*

---

## 📋 Table of Contents

- [Core Mechanics & Theme](#-core-mechanics--theme)
- [Defensive Arsenal (Towers & Upgrades)](#-defensive-arsenal-towers--upgrades)
- [Power-Up Tiles (Site Resources)](#-power-up-tiles-site-resources)
- [Hostile Creep Archetypes](#-hostile-creep-archetypes)
- [Blueprint Contracts (Levels)](#-blueprint-contracts-levels)
- [Union Hall (Meta-Progression Talent Tree)](#-union-hall-meta-progression-talent-tree)
- [Technical Architecture](#-technical-architecture)
- [Hardware Target & Performance](#-hardware-target--performance)
- [Project Layout](#-project-layout)
- [Local Setup & Verification](#-local-setup--verification)
- [Controls](#-controls)
- [License](#-license)

---

## 🎮 Core Mechanics & Theme

In **Jobsite Defense**, enemies march across designated jobsite access roads towards the final inspection exit. If creeps escape off-screen, client patience drops; if patience reaches zero, the contract is cancelled (**Game Over**). Eliminating creeps awards project budget cash to finance additional equipment, upgrades, or emergency liquidations.

- **Economy**: Starts with \$1,500 budget (or \$1,750 with Union Dues) and 100 client patience.
- **Liquidation ("Sell")**: Dismantling any deployed tower refunds **70%** of all invested capital (base purchase cost + upgrade expenses).
- **Radial Build Menu**: Contextual 8-angle orbit menu placed on grid cells, strictly clamped within screen bounds to guarantee clickability on perimeter cells.

---

## 🛠️ Defensive Arsenal (Towers & Upgrades)

All towers inherit from the unified `Tower` protocol base (Render Layer 20) and are registered in `BUILDABLE`:

| Tower | Cost | Base Stats | Tier 2 Upgrade | Tier 3 Upgrade |
|---|---|---|---|---|
| **Nail Gunner** | \$500 | Cooldown: 0.8s<br>Range: 120px<br>Damage: 25 HP (Hitscan) | **Pneumatic Overdrive** (\$300)<br>• Cooldown halved (0.4s) | **The Scaffold** (\$800)<br>• Range doubled (240px)<br>• Enables Anti-Air targeting |
| **Concrete Pump** | \$750 | Cooldown: 2.5s<br>Range: 150px<br>Damage: 5 HP (Splash)<br>Speed: 250 px/s | **Quick-Dry** (\$450)<br>• Slow debuff strengthened to 0.2x speed | **Cement Truck** (\$1,000)<br>• Splash radius doubled to 180px (3.0 cells) |
| **Tarp Cannon** | \$400 | Cooldown: 0.3s<br>Range: 160px<br>Damage: 10 HP (Homing)<br>Anti-Air Priority | **Sticky Resin** (\$500)<br>• Applies 0.3x speed debuff for 3.0s to flying creeps | **EMP Net** (\$1,200)<br>• Delivers 1.5s stun debuff with mid-flight retargeting |

---

## ⚡ Power-Up Tiles (Site Resources)

Pre-positioned resource cells buff towers constructed directly on top of them:

| Tile | Stat Multiplier | Visual Accent | Flavor |
|---|---|---|---|
| **Yeti Cooler** 🧊 | Attack Speed ×1.25 | Azure Blue (`#64B4FF`) | *"Hydrated workers swing faster."* |
| **Heavy Air Compressor** 💨 | Damage ×1.50 | Construction Orange (`#FFB43C`) | *"More PSI, more penetration."* |
| **Extension Cord** 🔌 | Attack Range ×1.25 | High-Vis Green (`#3CDC78`) | *"Reach those far corners."* |

---

## 🪚 Hostile Creep Archetypes

Creeps navigate route waypoints at Render Layer 10 with predictive intercept leading and status debuffs:

| Enemy | Stats | Bounty | Behavior & Abilities |
|---|---|---|---|
| **Rotted 2×4** | 100 HP<br>120 px/s | \$15 | Standard foot soldier. Balanced health and speed. |
| **HOA Board Member** | 1 HP<br>180 px/s | \$5 | High-speed swarm unit rushing the site in clusters. |
| **Rain Cloud** 🌧️ | 60 HP<br>80 px/s | \$20 | **Flying hazard**: Bypasses ground roads, flying directly from entrance to exit. Immune to ground-only towers. |
| **OSHA Inspector** ⚠️ | 2,500 HP<br>40 px/s | \$100 | **Boss Encounter**: Radiates a 150px (2.5 cells) **Stop-Work Order aura** disabling all nearby towers. Aura is suppressed when stunned; possesses a 3.0s diminishing-returns lockout to prevent permanent stunlocking. Costs 20 client patience on leak. |

---

## 📐 Blueprint Contracts (Levels)

Contracts are declaratively defined in JSON blueprints located in `levels/`:

1. **Contract 1: "The Foundation" (`level_1.json`)**
   - Single primary thoroughfare with winding corners.
   - Standard 5-wave progression introducing basic creeps and culminating in the OSHA Inspector boss.
2. **Contract 2: "The Subcontract" (`level_2.json`)**
   - Multi-route topology featuring concurrent **main** and **flank** approach vectors.
   - Split-wave incursions demanding balanced defense distribution.

---

## 🏛️ Union Hall (Meta-Progression Talent Tree)

Victory awards spendable **Union Equity** equal to remaining client patience. Equity can be invested in permanent talent tree perks in the Union Hall:

| Perk | Equity Cost | Effect |
|---|---|---|
| **Union Dues** | 100 Eq | +\$250 Starting Project Budget on all matches |
| **Heavy Duty Nails** | 250 Eq | Nail Gunner Base Damage +5 (25 → 30 HP) |
| **Overtime** | 150 Eq | Wave Breather Cooldowns extended from 15s to 20s |

**Resilient Atomic Save Persistence:**
- Persists to OS user application data directories:
  - Windows: `%APPDATA%\JobsiteDefense\save_data.json`
  - POSIX: `~/.local/share/JobsiteDefense/save_data.json`
- Writes to temporary files with `os.fsync()` and handles Windows file-locking contention with exponential backoff retries.
- UI transactions feature automatic in-memory state rollbacks if persistence encounters I/O failures.

---

## 🏗️ Technical Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                              SceneManager                              │
│   TitleScene  ◄──►  LevelSelectScene  ◄──►  TalentTreeScene (Modal)    │
│                           │                                            │
│                           ▼                                            │
│                    GameplayScene  ◄──►  PauseScene (Modal)             │
│                           │                                            │
│         ┌─────────────────┴─────────────────┐                          │
│         ▼                                   ▼                          │
│  Static Surface Cache                World Context                     │
│  (1 Blit: Grass, Road, Grid, Tiles)  ├── LevelData (Multi-Path)        │
│                                      ├── Economy (Budget, Patience)    │
│                                      ├── Towers (Layer 20)             │
│                                      ├── Enemies (Layer 10)            │
│                                      ├── Projectiles (Layer 30)        │
│                                      ├── WaveManager (Layer 5)         │
│                                      ├── RadialMenu (Layer 90)         │
│                                      └── Event Bus (GameEvent Queue)   │
└────────────────────────────────────────────────────────────────────────┘
```

- **Stack-Based Scene Architecture**: Formal `Scene` protocol supporting modal overlays (`PauseScene`), state replacements, and backstack transitions.
- **Render Layer Ordering**: Deterministic draw-order sorting:
  - Layer 5: `WaveManager`
  - Layer 10: `Enemy` entities
  - Layer 20: `Tower` entities
  - Layer 30: `Projectile` entities (`ConcreteGlob`, `TarpProjectile`)
  - Layer 90: `RadialMenu` UI
- **Event Bus (`GameEvent`)**: Structured telemetry stream emitting `SHOT`, `KILL`, `LEAK`, `BUILD`, `SELL`, `UPGRADE`, `STUN`, and `SPLASH` events for decoupled particle, audio, and achievement systems.
- **Predictive Intercept Leading**: `ConcretePump` executes an iterative 3-pass lead solver over future waypoint travel budgets, accounting for speed debuffs and stun intervals.
- **Homing Ballistics**: `TarpProjectile` features real-time vector homing and mid-flight retargeting to the nearest live hostile if its primary target is eliminated in transit.

---

## 💻 Hardware Target & Performance

Engineered specifically for low-overhead execution on integrated mobile graphics:

| Target Spec | Benchmark Value |
|---|---|
| **CPU** | Intel Core i7-7500U (2 cores / 4 threads, 2.70 GHz) |
| **RAM** | 16 GB DDR4 |
| **GPU** | Intel HD Graphics 620 (Integrated) |
| **Display Mode** | 960 × 720, `pygame.SCALED`, VSync enabled |
| **Frame Rate** | Locked 60 FPS (dt capped at ≤ 0.05s) |

### Performance Optimizations:
1. **Static Surface Caching**: Background grass, roads, power-up labels, and grid lines are pre-baked onto an optimized hardware display surface once at level load, collapsing 75+ individual raster draw calls into a **single DMA blit** per frame.
2. **Dirty-Flag Entity Sorting**: `GameplayScene._build_entity_list()` utilizes a `_dirty: bool` cache, skipping array allocations and $O(N \log N)$ layer sorts during idle frames and input polling passes.
3. **Sparse Data Structures**: Fast spatial queries using `dict[tuple[int, int], Tower]` and `frozenset[tuple[int, int]]` road sets instead of dense 2D matrices.

---

## 📁 Project Layout

```
jobsite-defense/
├── levels/
│   ├── level_1.json         # Blueprint: The Foundation (Single-route)
│   └── level_2.json         # Blueprint: The Subcontract (Multi-route)
├── src/
│   ├── economy.py           # Budget and patience management
│   ├── enemy.py             # Creep base, archetypes, status modifiers, prediction
│   ├── grid.py              # Grid dimensioning and coordinate math
│   ├── level.py             # Declarative JSON level loader & validation
│   ├── main.py              # Display init & primary application entry point
│   ├── projectile.py        # ConcreteGlob AoE & TarpProjectile homing
│   ├── protocols.py         # Entity, Clickable, and Projectile protocols
│   ├── render.py            # Static background layer caching
│   ├── save.py              # Atomic JSON persistence & user-data directory resolution
│   ├── scene.py             # Scene protocol, SceneManager, Title, LevelSelect, Gameplay
│   ├── settings.py          # Global constants, colors, and tuning values
│   ├── talent_ui.py         # Union Hall meta-progression store
│   ├── tower.py             # Tower base, NailGunner, ConcretePump, TarpCannon
│   ├── ui.py                # Contextual Radial Build/Upgrade/Sell menu
│   ├── wave.py              # WaveSpec definitions and WaveManager state machine
│   └── world.py             # World simulation context and GameEvent bus
├── tests/
│   ├── conftest.py          # Session-scoped headless SDL dummy configuration
│   ├── test_economy.py      # Spending, earnings, patience limits
│   ├── test_enemy.py        # Movement, prediction, boss auras, stun lockouts
│   ├── test_level.py        # Level parsing, wave validation, road geometry
│   ├── test_save.py         # Atomic persistence, file locks, talent rollback
│   ├── test_scene.py        # Scene stack, transitions, entity caching
│   ├── test_tower.py        # Combat, leading, upgrades, air restrictions
│   ├── test_ui.py           # Radial menu clamping, 3-tower registry, max tier
│   ├── test_wave.py         # WaveManager cooldown and spawning
│   └── test_world.py        # Construction, liquidation, event bus emission
├── pyproject.toml           # Project metadata, dependencies, ruff, mypy, pytest configs
├── requirements.txt         # Pinned runtime dependencies
├── run.py                   # Convenience executable entry point
├── ARCHITECTURE.md          # Comprehensive architectural reference
└── README.md                # System documentation
```

---

## 🚀 Local Setup & Verification

### Prerequisites
- **Python 3.11+**
- **Git**

### Installation

```bash
# Clone repository
git clone https://github.com/blairmichaelg/jobsite-defense.git
cd jobsite-defense

# Create and activate virtual environment
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Game

```bash
# Via convenience script
python run.py

# Or as a module
python -m src.main
```

### Running Verification Gates

```bash
# Run full unit test suite (138+ automated tests)
pytest -v

# Run strict static type checking (0 errors required)
mypy --strict src/ tests/

# Run fast code linting
ruff check src/ tests/
```

---

## 🎮 Controls

| Action | Control |
|---|---|
| **Inspect / Build / Upgrade** | `Left Click` on grass or tower cell |
| **Dismiss Menu / Deselect** | `Right Click` or `ESC` |
| **Select Level Contract** | `1` / `2` in Level Select |
| **Access Talent Tree** | `T` in Title Menu |
| **Access Level Select** | `L` in Title Menu |
| **Pause / Resume Game** | `P` or `ESC` |
| **Restart Failed / Won Match** | `R` (only active on Game Over or Victory screens) |
| **Quit Game / Back to Menu** | `ESC` / `Q` |

---

## 📄 License

Proprietary — All rights reserved.
