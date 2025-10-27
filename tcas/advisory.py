from enum import Enum, auto
from typing import Dict
from .models import Aircraft, Advisory, AdvisoryType
from .threat import classify_contact
import config

class State(Enum):
    CLEAR = auto()
    TA = auto()
    RA_CLIMB = auto()
    RA_DESCEND = auto()
    RA_MAINTAIN = auto()

class AdvisoryLogic:
    """
    Deterministic, conflict-free selection of a single advisory per ownship,
    across all intruders (pick worst-case).
    """
    def __init__(self) -> None:
        pass

    def step(self, own: Aircraft, rels: Dict[str, tuple]) -> Advisory:
        # Aggregate the "worst" advisory across all intruders.
        priority = {
            AdvisoryType.CLEAR: 0,
            AdvisoryType.TA: 1,
            AdvisoryType.RA_MAINTAIN: 2,
            AdvisoryType.RA_CLIMB: 3,
            AdvisoryType.RA_DESCEND: 3,
        }
        best = (AdvisoryType.CLEAR, "Clear")

        for cs, (rel_pos, rel_vel, rel_alt) in rels.items():
            kind, reason = classify_contact(rel_pos, rel_vel, rel_alt)
            if priority[kind] > priority[best[0]]:
                best = (kind, f"{reason} vs {cs}")

        # Determinism: if equal priority RA_CLIMB/RA_DESCEND conflicts, prefer the command
        # that increases |vertical separation| relative to current intruder set.
        kind, reason = best
        return Advisory(kind=kind, reason=reason)

def apply_command(own: Aircraft):
    """ Nudge vertical speed when RA active (very simplified). """
    if own.advisory.kind == AdvisoryType.RA_CLIMB:
        own.climb_fps = max(own.climb_fps, 15.0)   # ~900 fpm
    elif own.advisory.kind == AdvisoryType.RA_DESCEND:
        own.climb_fps = min(own.climb_fps, -15.0)
    elif own.advisory.kind == AdvisoryType.RA_MAINTAIN:
        own.climb_fps = 0.0
    else:
        # gentle decay toward trimmed
        own.climb_fps *= 0.98
