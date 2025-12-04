Simplified TCAS II Simulation
============================================================

Overview
------------------------------------------------------------
This project implements a software-based approximation of **TCAS II, Version 7.1**, including
Traffic Advisories (TA), Resolution Advisories (RA), strengthened RAs, preventive guidance,
reversals, RA maintain logic, and safety inhibition rules. The system models aircraft encounters
in real time, visualizes TCAS symbology, and supports controlled fault injection to evaluate
resilience to degraded sensor inputs. A complementary **NuSMV formal verification model**
exhaustively checks key advisory safety properties.

Although simplified, the implementation follows published TCAS II v7.1 thresholds and logic
structures documented by the FAA.

------------------------------------------------------------
Features
------------------------------------------------------------
### **Core TCAS II (v7.1) Advisory Logic**
- Sensitivity Level (SL) selection by ownship altitude.
- TA and RA evaluation using:
  - Tau thresholds (τ_RA, τ_TA)
  - DMOD (horizontal miss distance threshold)
  - ZTHR (vertical miss distance threshold)
  - ALIM (minimum required vertical separation for RA)
- Corrective RAs: Climb, Descend, Crossing Climb/Descend.
- Strengthened RAs: Increase Climb/Descent.
- Negative / Reduce RAs: Level Off.
- Preventive RAs: Do Not Climb / Do Not Descend / Maintain Vertical Speed.
- Reversal RAs: “Climb, climb NOW” / “Descend, descend NOW”.
- Maintain RA logic when leaving RA but still within TA envelope.
- HMD filtering to suppress TAs/RAs when lateral miss distance is large.
- RA inhibition below low-altitude thresholds (<1000 ft AGL).

### **Multi-Aircraft Coordination (Simplified)**
- Intruders select complementary RA senses (up vs. down) when both are TCAS-equipped.
- Basic coordination logic prevents conflicting vertical advisories.

### **Sensing and Fault Injection**
- True aircraft motion remains correct; only sensed values are corrupted.
- Supports:
  - **Bad altitude bias** (positive or negative)
  - **Bad vertical-speed bias**
  - **No-TCAS intruder** (non-cooperative)
- Logs include both true and sensed geometry to evaluate correctness.

### **Visualization**
- Radar-style Pygame display with TCAS symbols:
  - Open diamond – other traffic  
  - Filled diamond – proximate traffic  
  - Amber circle – TA  
  - Red square – RA  
- Dynamic HUD showing:
  - Advisory text and aural phrasing  
  - Ownship altitude and vertical speed  
  - Current RA mode and strengthening state  

### **Scenario Framework**
Includes **16 predefined scenarios**, grouped into:
- Baseline encounters (head-on, crossing, overtake, parallel)
- Advisory behavior cases (strengthening, immediate RA, descend vs. level, high vertical separation)
- Multi-aircraft and coordinated encounters (multi-threat, two-opposite, parity)
- Edge-case geometry (NMAC-edge)
- Fault-injected and RA-inhibited scenarios (Bad Altitude, Bad VS, Low Altitude, No-TCAS)

Each scenario comes with a generated CSV log for post-run analysis.

### **Formal Verification (NuSMV)**
A dedicated abstract TCAS model evaluates:
- RA inhibition below minimum altitude
- RA suppression when HMD is large
- Advisory stability (hysteresis)
- Eventual reachability of CLEAR state
- Partial coordination correctness

This ensures coverage of encounter conditions not easily captured through simulation alone.

------------------------------------------------------------
Project Structure
------------------------------------------------------------
```bash
tcas_sim/
├─ run.py # Main entry point
├─ analysis.py # Log post-processing tools
├─ config.py # Thresholds and runtime parameters
│
├─ tcas/ # Core TCAS logic
│ ├─ advisory.py # Advisory state machine + RA/TA selection
│ ├─ threat.py # TA/RA envelope evaluation (Tau, DMOD, ZTHR, ALIM)
│ ├─ tracking.py # Relative motion, CPA, closure rate
│ ├─ sensing.py # Sensed-value snapshot (fault injection)
│ ├─ models.py # Advisory types, aircraft model
│ ├─ math_utils.py # Kinematic helpers
│ ├─ io.py # CSV import/export
│ └─ bus.py # Event distribution
│
├─ sim/
│ ├─ world.py # Manages aircraft states and time stepping
│ └─ scenarios.py # Definitions for the 16 test encounters
│
├─ viz/ # Pygame visualization
│ ├─ radar_display.py
│ ├─ hud.py
│ ├─ colors.py
│ └─ pygame_app.py
│
├─ formal_model/
│ └─ tcas.smv # Abstract TCAS model for model checking
│
└─ data/
├─ OWN_.csv # Ownship data for scenarios
├─ scennario/
│ └─ INT_.csv # Intruder data for scenarios
└─ data/
 └─ tcas_log_*.csv # Logged advisory outputs
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
Prepare a CSV file for ownship and intruder (example: data/OWN.csv):
```bash
time_s,aircraft_id,df,icao24,mode,altitude_ft,vertical_rate_fpm,on_ground,tcas_equipped,identity,squawk,range_nm,bearing_deg,range_rate_kt
0,OWN_NOTCAS,17,ABC138,S,15000,0,0,1,OWN_NOTCAS,7000,0,0,0
```

Run:
```bash
  python run.py --ownship data/OWN001.csv --input data/scenario/
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
- Advisory type (TA/RA/CLEAR)
- RA subtype (strengthened, reversal, preventive)
- Aural annunciation text
- Ownship state and vertical speed
- Fault indicators (bad altitude, bad VS, no-TCAS)

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
- pyttsx3 2.91
- pytest
- hypothesis

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
