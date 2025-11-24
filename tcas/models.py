from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
from enum import Enum, auto


class AdvisoryType(Enum):
    CLEAR = auto()
    TA = auto()

    # Basic RAs
    RA_CLIMB = auto()           
    RA_DESCEND = auto()         
    RA_MAINTAIN = auto()        

    # Strengthened / weakened RAs
    RA_INCREASE_CLIMB = auto()   
    RA_INCREASE_DESCEND = auto() 
    RA_REDUCE_CLIMB = auto()     
    RA_REDUCE_DESCEND = auto()   

    # Altitude-crossing RAs
    RA_CROSSING_CLIMB = auto()   
    RA_CROSSING_DESCEND = auto() 


@dataclass
class Advisory:
    kind: AdvisoryType = AdvisoryType.CLEAR
    reason: str = ""


@dataclass
class Aircraft:
    # -------------------------------
    # Basic positional state
    # -------------------------------
    callsign: str
    pos_m: Tuple[float, float]          # (x,y) meters
    vel_mps: Tuple[float, float]        # horizontal velocity vector
    alt_ft: float                       # altitude in ft
    climb_fps: float                    # vertical speed ft/s

    # -------------------------------
    # TCAS-related metadata
    # -------------------------------
    icao24: Optional[str] = None
    mode: Optional[str] = None          # Mode A/C/S etc.
    squawk: Optional[str] = None
    identity: Optional[str] = None
    on_ground: bool = False             # from CSV on_ground=0/1
    tcas_equipped: bool = True          # whether the aircraft has TCAS-II

    # -------------------------------
    # Manual control / UI
    # -------------------------------
    advisory: Advisory = field(default_factory=Advisory)
    color: Tuple[int, int, int] = (200, 200, 220)

    control_mode: str = "AUTO"          # "AUTO" or "MANUAL"
    manual_cmd: Optional[str] = None    # "CLIMB", "DESCEND", "MAINTAIN"
    target_climb_fps: Optional[float] = None

    def step(self, dt: float):
        """Integrate horizontal and vertical motion."""
        self.pos_m = (
            self.pos_m[0] + self.vel_mps[0] * dt,
            self.pos_m[1] + self.vel_mps[1] * dt
        )
        self.alt_ft += self.climb_fps * dt


TrafficPicture = Dict[str, Aircraft]
