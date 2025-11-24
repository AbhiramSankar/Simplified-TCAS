from enum import Enum, auto
from typing import Dict, List, Tuple
from .models import Aircraft, Advisory, AdvisoryType
from .threat import classify_contact, closing_tau_and_dcpA
import config


from enum import Enum, auto
from typing import Dict, List, Tuple
from .models import Aircraft, Advisory, AdvisoryType
from .threat import classify_contact, closing_tau_and_dcpA
import config


class State(Enum):
    CLEAR = auto()
    TA = auto()
    RA_CLIMB = auto()
    RA_DESCEND = auto()
    RA_MAINTAIN = auto()

# Helper: classify RA vertical sense
# +1 = up, -1 = down, 0 = neutral/preventive
UP_RAS = {
    AdvisoryType.RA_CLIMB,
    AdvisoryType.RA_INCREASE_CLIMB,
    AdvisoryType.RA_REDUCE_DESCEND,   # reducing descent moves toward up/level
    AdvisoryType.RA_CROSSING_CLIMB,
}
DOWN_RAS = {
    AdvisoryType.RA_DESCEND,
    AdvisoryType.RA_INCREASE_DESCEND,
    AdvisoryType.RA_REDUCE_CLIMB,     # reducing climb moves toward down/level
    AdvisoryType.RA_CROSSING_DESCEND,
}
NEUTRAL_RAS = {
    AdvisoryType.RA_MAINTAIN,
}


def ra_vertical_direction(kind: AdvisoryType) -> int:
    """Return +1 (up), -1 (down), or 0 (neutral) for a given RA kind."""
    if kind in UP_RAS:
        return +1
    if kind in DOWN_RAS:
        return -1
    if kind in NEUTRAL_RAS:
        return 0
    return 0


# Map an RA to its "coordinated opposite" vertical sense
RA_FLIP_MAP = {
    AdvisoryType.RA_CLIMB:           AdvisoryType.RA_DESCEND,
    AdvisoryType.RA_DESCEND:         AdvisoryType.RA_CLIMB,
    AdvisoryType.RA_INCREASE_CLIMB:  AdvisoryType.RA_INCREASE_DESCEND,
    AdvisoryType.RA_INCREASE_DESCEND:AdvisoryType.RA_INCREASE_CLIMB,
    AdvisoryType.RA_REDUCE_CLIMB:    AdvisoryType.RA_REDUCE_DESCEND,
    AdvisoryType.RA_REDUCE_DESCEND:  AdvisoryType.RA_REDUCE_CLIMB,
    AdvisoryType.RA_CROSSING_CLIMB:  AdvisoryType.RA_CROSSING_DESCEND,
    AdvisoryType.RA_CROSSING_DESCEND:AdvisoryType.RA_CROSSING_CLIMB,
}


class AdvisoryLogic:

    def step(self, own: Aircraft, rels: Dict[str, tuple]) -> Advisory:
        ra_threats: List[dict] = []
        ta_threats: List[dict] = []

        for cs, (rel_pos, rel_vel, rel_alt) in rels.items():
            kind, reason = classify_contact(
                own.alt_ft,
                rel_pos,
                rel_vel,
                rel_alt,
                prev_state=own.advisory.kind,
            )
            tau, d_cpa = closing_tau_and_dcpA(rel_pos, rel_vel)

            entry = {
                "cs": cs,
                "kind": kind,
                "reason": reason,
                "tau": tau,
                "d_cpa": d_cpa,
                "rel_alt_ft": rel_alt,
            }

            if kind.name.startswith("RA_"):
                ra_threats.append(entry)
            elif kind == AdvisoryType.TA:
                ta_threats.append(entry)

        # ----- RA aggregation -----
        if ra_threats:
            # Primary threat: smallest tau, then smallest dCPA
            primary = min(ra_threats, key=lambda e: (e["tau"], e["d_cpa"]))
            composite_kind = primary["kind"]

            extra = ""
            if len(ra_threats) > 1:
                extra = f", +{len(ra_threats)-1} other RA threats"

            reason = (
                f"{composite_kind.name} (primary {primary['cs']} "
                f"τ={primary['tau']:.1f}s d_cpa={primary['d_cpa']:.0f} m "
                f"Δalt={primary['rel_alt_ft']:.0f} ft{extra})"
            )
            return Advisory(kind=composite_kind, reason=reason)

        # ----- TA aggregation -----
        if ta_threats:
            primary = min(ta_threats, key=lambda e: (e["tau"], e["d_cpa"]))
            extra = ""
            if len(ta_threats) > 1:
                extra = f", +{len(ta_threats)-1} other TA threats"
            reason = (
                f"TA (primary {primary['cs']} τ={primary['tau']:.1f}s "
                f"d_cpa={primary['d_cpa']:.0f} m Δalt={primary['rel_alt_ft']:.0f} ft{extra})"
            )
            return Advisory(kind=AdvisoryType.TA, reason=reason)

        # ----- No threats -----
        return Advisory(kind=AdvisoryType.CLEAR, reason="Clear (no threats)")
    
def apply_command(own: Aircraft, override_manual: bool = False):

    # 0) Manual override first
    if own.control_mode == "MANUAL" and own.manual_cmd is not None:
        if override_manual:
            if own.manual_cmd == "CLIMB":
                own.climb_fps = max(own.climb_fps, own.target_climb_fps or 15.0)
            elif own.manual_cmd == "DESCEND":
                own.climb_fps = min(own.climb_fps, own.target_climb_fps or -15.0)
            elif own.manual_cmd == "MAINTAIN":
                own.climb_fps = 0.0
        return

    # 1) NON-TCAS aircraft → ignore all advisories
    if not own.tcas_equipped:
        # Prevent RA symbols from showing
        if own.advisory.kind.name.startswith("RA_"):
            own.advisory.kind = AdvisoryType.TA if "TA" in own.advisory.reason.upper() else AdvisoryType.CLEAR
        return

    # 2) TCAS RA logic (unchanged below)
    k = own.advisory.kind

    if k in (AdvisoryType.RA_CLIMB, AdvisoryType.RA_CROSSING_CLIMB):
        own.climb_fps = max(own.climb_fps, 15.0)

    elif k in (AdvisoryType.RA_DESCEND, AdvisoryType.RA_CROSSING_DESCEND):
        own.climb_fps = min(own.climb_fps, -15.0)

    elif k == AdvisoryType.RA_INCREASE_CLIMB:
        own.climb_fps = max(own.climb_fps, 25.0)

    elif k == AdvisoryType.RA_INCREASE_DESCEND:
        own.climb_fps = min(own.climb_fps, -25.0)

    elif k == AdvisoryType.RA_REDUCE_CLIMB:
        if own.climb_fps > 5.0:
            own.climb_fps = 5.0
        else:
            own.climb_fps *= 0.8

    elif k == AdvisoryType.RA_REDUCE_DESCEND:
        if own.climb_fps < -5.0:
            own.climb_fps = -5.0
        else:
            own.climb_fps *= 0.8

    elif k == AdvisoryType.RA_MAINTAIN:
        own.climb_fps = 0.0

    else:
        # 3) No RA
        if own.control_mode == "MANUAL" and own.manual_cmd is not None:
            # Manual mode: let pilot commands bias the vertical speed
            if own.manual_cmd == "CLIMB":
                own.climb_fps = own.climb_fps * 0.7 + (own.target_climb_fps or 10.0) * 0.3
            elif own.manual_cmd == "DESCEND":
                own.climb_fps = own.climb_fps * 0.7 + (own.target_climb_fps or -10.0) * 0.3
            elif own.manual_cmd == "MAINTAIN":
                own.climb_fps *= 0.9
