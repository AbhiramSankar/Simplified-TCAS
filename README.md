Simplified TCAS II Simulation
============================================================

Overview
------------------------------------------------------------
This project implements a Simplified Traffic Collision Avoidance System (TCAS II)
using Python and Pygame. It simulates real-time aircraft encounters, computing
Traffic Advisories (TA) and Resolution Advisories (RA) based on relative motion,
altitude, and time to closest approach.

The simulation visualizes TCAS symbology (diamonds, circles, squares) and altitude
tags on a radar-like display, with a side panel showing advisories, control inputs,
and ownship altitude.

------------------------------------------------------------
Features
------------------------------------------------------------
- Real-time TCAS logic (TA, RA, and CLEAR states) with automatic reset.
- Radar visualization with TCAS II symbols:
  * Unfilled diamond – Other traffic
  * Filled diamond – Proximate traffic
  * Amber circle – Traffic Advisory (TA)
  * Red square – Resolution Advisory (RA)
- CSV-based flight data input or built-in scenario mode.
- Manual control override (pilot climb/descend inputs).
- Dynamic side HUD with controls and aircraft status.
- Automatic removal of off-radar contacts.

------------------------------------------------------------
Project Structure
------------------------------------------------------------
```bash
tcas_sim/
├─ run.py                 : Entry point
├─ config.py              : Global configuration
│
├─ tcas/                  : Core TCAS logic
│  ├─ advisory.py         : Advisory decision logic
│  ├─ threat.py           : Threat classification and TA/RA logic
│  ├─ tracking.py         : Relative motion and closure rate computation
│  ├─ sensing.py          : Simplified sensing snapshot
│  ├─ math_utils.py       : Helper math functions
│  ├─ models.py           : Data models (Aircraft, Advisory types)
│  ├─ io.py               : CSV I/O utilities
│  └─ bus.py              : Event bus
│
├─ simulation/            : Simulation control
│  ├─ world.py            : Manages aircraft states and steps
│  └─ scenarios.py        : Built-in demo scenarios
│
└─ viz/                   : Visualization (Pygame)
   ├─ radar_display.py    : Radar drawing logic
   ├─ hud.py              : Side panel with controls and advisories
   ├─ colors.py           : Common color definitions
   └─ pygame_app.py       : Pygame rendering loop
```

------------------------------------------------------------
Installation
------------------------------------------------------------

1. Clone or download the repository:
```bash
   git clone https://github.com/AbhiramSankar/Simplified-TCAS.git
   cd Simplified-TCAS
```

2. Create and activate a virtual environment:
```bash
   python -m venv venv
   source venv/bin/activate        (Linux/macOS)
   venv\Scripts\activate           (Windows)
```

3. Install dependencies:
```bash
   pip install -r requirements.txt
```


------------------------------------------------------------
Running the Simulation
------------------------------------------------------------

Option 1 - Using a CSV Input File:
----------------------------------
Prepare a CSV file (example: data/sample_flightplan.csv):
```bash
callsign,x_m,y_m,vel_x_mps,vel_y_mps,alt_ft,climb_fps,color_r,color_g,color_b
OWN001,0,0,150,0,10000,0,255,255,255
INT001,10000,0,-150,0,10500,-10,255,180,0
INT002,-8000,-5000,140,70,11800,-5,255,255,255
```

Run:
```bash
   python run.py --input data/sample_flightplan.csv
```

Option 2 - Using Built-in Scenarios:
------------------------------------
```bash
   python run.py
   Press 1, 2, or 3 to load predefined encounters (Head-On, Crossing, Overtake).
```

------------------------------------------------------------
Controls
------------------------------------------------------------
```bash
SPACE        : Pause / Resume
R            : Reload scenario or CSV
TAB          : Select next aircraft
M            : Toggle manual mode
O            : Toggle manual override
UP / DOWN    : Adjust climb or descent
C            : Clear manual command
1 / 2 / 3    : Load scenarios (only in scenario mode)
ESC          : Exit simulation
```
------------------------------------------------------------
Display Elements
------------------------------------------------------------
Left Side - TCAS Radar:
- Ownship (white triangle) centered.
- Intruders within 12 NM range.
- Altitude tags in hundreds of feet (+10↑, -08↓).

Right Side - HUD Panel:
- Time, selected aircraft, override mode.
- Active advisories and commands.
- Ownship altitude at bottom.

------------------------------------------------------------
How It Works
------------------------------------------------------------
1. World updates aircraft each frame (simulation/world.py)
2. Sensing snapshots aircraft states (tcas/sensing.py)
3. Tracking computes relative motion (tcas/tracking.py)
4. Threat logic classifies intruders (tcas/threat.py)
5. Advisory logic applies vertical guidance (tcas/advisory.py)
6. Visualization updates display using Pygame (viz/)

------------------------------------------------------------
Requirements
------------------------------------------------------------
- Python 3.8 or higher
- Pygame 2.5 or higher
- Numpy (optional)

------------------------------------------------------------
Notes
------------------------------------------------------------
- This TCAS logic is simplified and not certified for real aviation use.
- Intended purely for academic and simulation purposes.

------------------------------------------------------------
Author
------------------------------------------------------------
Abhiram Sankar\
Ontario Tech University\
Simplified TCAS II Simulation
