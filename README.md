# 🏗️ Jobsite Defense

**A 2D Tower Defense game where the construction site fights back.**

Defend the jobsite from waves of code violations, rotten lumber, and
overzealous inspectors. Place tool-towers, collect resource power-ups,
and keep the framers framing.

> *"If the building don't get 'em, the nail gun will."*

---

## 📋 Table of Contents

- [Game Concept](#game-concept)
- [Technical Stack](#technical-stack)
- [Hardware Target](#hardware-target)
- [Project Structure](#project-structure)
- [Local Setup](#local-setup)
- [Running the Game](#running-the-game)
- [Architecture](#architecture)
- [Roadmap](#roadmap)
- [License](#license)

---

## 🎮 Game Concept

### Theme — *Construction / Framing*

Enemies march down the **road** (a dirt path through the jobsite). You
place **tool-towers** on adjacent grid cells to stop them. Certain cells
contain **resource power-ups** that buff nearby towers.

### Towers (Tools)

| Tower | Role | Description |
|---|---|---|
| **Nail Gunner** | Basic single-target | Rapid-fire framing nails. Cheap, reliable, bread-and-butter. |
| **Concrete Pump** | Splash / Slowdown | Sprays wet concrete in an area, slowing enemies and dealing splash damage. |
| **Greenhorn w/ Estwing** | Melee burst | A new guy swinging wildly. High burst damage in a tiny radius. |
| **LVL Crane Drop** | AoE artillery | Drops an engineered lumber beam from orbit. Long cooldown, massive area. |

### Power-Up Tiles (Resources)

| Tile | Effect | Flavor |
|---|---|---|
| **Yeti Cooler** 🧊 | Attack speed ↑ | "Hydrated workers swing faster." |
| **Heavy Air Compressor** 💨 | Damage ↑ | "More PSI, more penetration." |
| **Extension Cord** 🔌 | Range ↑ | "Reach those far corners." |

### Enemies (Creeps)

| Enemy | Type | Description |
|---|---|---|
| **Rotted 2×4s** | Basic | Shambling lumber. Slow, weak, comes in bulk. |
| **HOA Board Members** | Swarm | Fast, annoying, arrive in large groups with clipboards. |
| **OSHA Inspector** | Boss | Tanky. Slows your towers with "citations." |

---

## 🛠️ Technical Stack

| Component | Choice |
|---|---|
| Language | Python 3.11 (strict type hints) |
| Engine | [Pygame-CE](https://pyga.me/) `2.5.8` |
| Rendering | Software raster (SDL2 via Pygame-CE) |
| Data model | Sparse collections (`frozenset`, `dict`) — no dense 2D arrays |
| VCS | Git — single-branch (`main`), direct commits |

---

## 💻 Hardware Target

| Spec | Value |
|---|---|
| CPU | Intel Core i7-7500U (2C/4T, 2.7 GHz) |
| RAM | 16 GB DDR4 |
| GPU | Intel HD Graphics 620 (integrated) |
| OS | Windows 10 |

The game is designed to run well on integrated graphics at **60 FPS**.

---

## 📁 Project Structure

```
jobsite-defense/
├── src/
│   ├── __init__.py
│   ├── main.py          # Entry point & game loop
│   ├── settings.py      # Constants & configuration
│   ├── grid.py          # Grid rendering & cell logic
│   ├── road.py          # Road data & rendering
│   ├── enemy.py         # Enemy entity & movement
│   └── powerup.py       # Power-up tile data & rendering
├── assets/              # (future) sprites, sounds
├── tests/               # (future) unit tests
├── .gitignore
├── requirements.txt
├── README.md
├── ARCHITECTURE.md
└── run.py               # Convenience launcher
```

---

## 🚀 Local Setup

### Prerequisites

- **Python 3.11+** ([download](https://www.python.org/downloads/))
- **Git** ([download](https://git-scm.com/downloads))

### Installation

```bash
# Clone the repository
git clone https://github.com/blairmichaelg/jobsite-defense.git
cd jobsite-defense

# Create a virtual environment
python -m venv .venv

# Activate it
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## ▶️ Running the Game

```bash
python run.py
```

Or directly:

```bash
python -m src.main
```

A **960 × 720** window will open showing the construction-site grid, the
dirt road, power-up tiles, and a test enemy (red circle) marching along
the waypoints.

---

## 🏛️ Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full data-model
documentation, game-loop diagram, and module responsibilities.

---

## 🗺️ Roadmap

| Phase | Milestone | Status |
|---|---|---|
| **1** | Rendering window, grid, road, moving enemy | 🟢 Current |
| **2** | Tower placement & basic shooting | ⬜ Planned |
| **3** | Enemy waves, health, scoring | ⬜ Planned |
| **4** | Power-up tile effects | ⬜ Planned |
| **5** | Sprites, sound, UI polish | ⬜ Planned |
| **6** | Boss mechanics (OSHA Inspector) | ⬜ Planned |

---

## 📄 License

TBD — All rights reserved until a license is chosen.
