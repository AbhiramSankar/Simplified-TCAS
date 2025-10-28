from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
from enum import Enum, auto

class AdvisoryType(Enum):
    CLEAR = auto()
    TA = auto()
    RA_CLIMB = auto()
    RA_DESCEND = auto()
    RA_MAINTAIN = auto()

@dataclass
class Advisory:
    kind: AdvisoryType = AdvisoryType.CLEAR
    reason: str = ""

@dataclass
class Aircraft:
    callsign: str
    pos_m: Tuple[float, float]    # (x,y) meters in world
    vel_mps: Tuple[float, float]  # horizontal velocity (m/s)
    alt_ft: float                 # altitude in feet
    climb_fps: float              # vertical speed in ft/s
    advisory: Advisory = field(default_factory=Advisory)
    color: Tuple[int, int, int] = (200, 200, 220)

    # New fields for manual control
    control_mode: str = "AUTO"   # "AUTO" or "MANUAL" - MANUAL means pilot input active
    manual_cmd: Optional[str] = None  # "CLIMB", "DESCEND", "MAINTAIN", or None
    target_climb_fps: Optional[float] = None  # target fps when manual command set

    def step(self, dt: float):
        self.pos_m = (self.pos_m[0] + self.vel_mps[0]*dt,
                      self.pos_m[1] + self.vel_mps[1]*dt)
        self.alt_ft += self.climb_fps * dt

TrafficPicture = Dict[str, Aircraft]
