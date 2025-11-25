from enum import Enum, auto
from typing import Dict, List, Tuple
from .models import Aircraft, Advisory, AdvisoryType
from .threat import classify_contact, closing_tau_and_dcpA
import config

# ============================================================
#   RA VERTICAL-SENSE CLASSIFICATION
# ============================================================

# +1 = up, -1 = down, 0 = neutral/preventive
UP_RAS = {
    AdvisoryType.RA_CLIMB,
    AdvisoryType.RA_INCREASE_CLIMB,
    AdvisoryType.RA_REDUCE_DESCEND,
    AdvisoryType.RA_CROSSING_CLIMB,
    AdvisoryType.RA_DO_NOT_DESCEND,   # preventive-up sense
}

DOWN_RAS = {
    AdvisoryType.RA_DESCEND,
    AdvisoryType.RA_INCREASE_DESCEND,
    AdvisoryType.RA_REDUCE_CLIMB,
    AdvisoryType.RA_CROSSING_DESCEND,
    AdvisoryType.RA_DO_NOT_CLIMB,     # preventive-down sense
}

NEUTRAL_RAS = {
    AdvisoryType.RA_MAINTAIN,
}

def ra_vertical_direction(kind: AdvisoryType) -> int:
    """Return +1 (up), -1 (down), or 0 (neutral) for any RA."""
    if kind in UP_RAS:
        return +1
    if kind in DOWN_RAS:
        return -1
    return 0


# ============================================================
#   TCAS II v7.1 RA COORDINATION OPPOSITE-SENSE MAP
# ============================================================

RA_FLIP_MAP = {
    AdvisoryType.RA_CLIMB:           AdvisoryType.RA_DESCEND,
    AdvisoryType.RA_DESCEND:         AdvisoryType.RA_CLIMB,

    AdvisoryType.RA_INCREASE_CLIMB:  AdvisoryType.RA_INCREASE_DESCEND,
    AdvisoryType.RA_INCREASE_DESCEND:AdvisoryType.RA_INCREASE_CLIMB,

    AdvisoryType.RA_REDUCE_CLIMB:    AdvisoryType.RA_REDUCE_DESCEND,
    AdvisoryType.RA_REDUCE_DESCEND:  AdvisoryType.RA_REDUCE_CLIMB,

    AdvisoryType.RA_CROSSING_CLIMB:  AdvisoryType.RA_CROSSING_DESCEND,
    AdvisoryType.RA_CROSSING_DESCEND:AdvisoryType.RA_CROSSING_CLIMB,

    # Preventive RAs
    AdvisoryType.RA_DO_NOT_CLIMB:    AdvisoryType.RA_DO_NOT_DESCEND,
    AdvisoryType.RA_DO_NOT_DESCEND:  AdvisoryType.RA_DO_NOT_CLIMB,
}

# ============================================================
#   Table-3 VERTICAL RATE BANDS
# ============================================================

FPM_TO_FPS = 1.0 / 60.0

# Corrective climb / descend
VS_CLIMB_MIN_FPS     = 1500.0 * FPM_TO_FPS
VS_CLIMB_MAX_FPS     = 2000.0 * FPM_TO_FPS
VS_CLIMB_NOMINAL_FPS = 1800.0 * FPM_TO_FPS

VS_DESC_MIN_FPS      = -2000.0 * FPM_TO_FPS
VS_DESC_MAX_FPS      = -1500.0 * FPM_TO_FPS
VS_DESC_NOMINAL_FPS  = -1800.0 * FPM_TO_FPS

# Maintain Climb / Maintain Descend
VS_MAINTAIN_MAX_UP_FPS   = 4400.0 * FPM_TO_FPS
VS_MAINTAIN_MIN_DOWN_FPS = -4400.0 * FPM_TO_FPS

# Strengthen RAs
VS_INCREASE_CLIMB_FPS   = 2500.0 * FPM_TO_FPS
VS_INCREASE_DESCEND_FPS = -2500.0 * FPM_TO_FPS

# Reduced RAs (limit to ±500 fpm)
VS_REDUCED_LIMIT_FPS = 500.0 * FPM_TO_FPS


# ============================================================
#   ADVISORY AGGREGATION LOGIC
# ============================================================

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

        # ---------------------------
        # RA aggregation
        # ---------------------------
        if ra_threats:
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

        # ---------------------------
        # TA aggregation
        # ---------------------------
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

        return Advisory(kind=AdvisoryType.CLEAR, reason="Clear (no threats)")


# ============================================================
#   APPLY COMMAND (VERTICAL SPEED)
# ============================================================

def apply_command(own: Aircraft, override_manual: bool = False):
    """
    Apply vertical speed based on RA logic (TCAS II Table-3).
    """

    # ---------------------------------------------------------
    # 0) Manual override (pilot)
    # ---------------------------------------------------------
    if own.control_mode == "MANUAL" and own.manual_cmd is not None:
        if override_manual:
            if own.manual_cmd == "CLIMB":
                own.climb_fps = max(
                    own.climb_fps,
                    own.target_climb_fps or VS_CLIMB_NOMINAL_FPS,
                )
            elif own.manual_cmd == "DESCEND":
                own.climb_fps = min(
                    own.climb_fps,
                    own.target_climb_fps or VS_DESC_NOMINAL_FPS,
                )
            elif own.manual_cmd == "MAINTAIN":
                own.climb_fps *= 0.8
        return

    # ---------------------------------------------------------
    # 1) Non-TCAS aircraft → ignore RA
    # ---------------------------------------------------------
    if not own.tcas_equipped:
        if own.advisory.kind.name.startswith("RA_"):
            own.advisory.kind = AdvisoryType.TA
        return

    # ---------------------------------------------------------
    # 2) TCAS AUTO: apply RA vertical-rate logic
    # ---------------------------------------------------------
    k = own.advisory.kind

    # -------- Corrective: CLIMB / CROSSING CLIMB
    if k in (AdvisoryType.RA_CLIMB, AdvisoryType.RA_CROSSING_CLIMB):
        own.climb_fps = VS_CLIMB_NOMINAL_FPS

    # -------- Corrective: DESCEND / CROSSING DESCEND
    elif k in (AdvisoryType.RA_DESCEND, AdvisoryType.RA_CROSSING_DESCEND):
        own.climb_fps = VS_DESC_NOMINAL_FPS

    # -------- Strengthen: Increase Climb/Descend
    elif k == AdvisoryType.RA_INCREASE_CLIMB:
        own.climb_fps = min(max(VS_INCREASE_CLIMB_FPS, own.climb_fps), VS_MAINTAIN_MAX_UP_FPS)

    elif k == AdvisoryType.RA_INCREASE_DESCEND:
        own.climb_fps = max(min(VS_INCREASE_DESCEND_FPS, own.climb_fps), VS_MAINTAIN_MIN_DOWN_FPS)

    # -------- Weaken: Reduce Climb/Reduce Descent
    elif k == AdvisoryType.RA_REDUCE_CLIMB:
        if own.climb_fps > VS_REDUCED_LIMIT_FPS:
            own.climb_fps = VS_REDUCED_LIMIT_FPS

    elif k == AdvisoryType.RA_REDUCE_DESCEND:
        if own.climb_fps < -VS_REDUCED_LIMIT_FPS:
            own.climb_fps = -VS_REDUCED_LIMIT_FPS

    # -------- Preventive RAs: DO NOT CLIMB / DO NOT DESCEND
    elif k == AdvisoryType.RA_DO_NOT_CLIMB:
        # Keep descent OK; prevent +VS
        if own.climb_fps > 0:
            own.climb_fps = 0.0
        if own.climb_fps < -VS_REDUCED_LIMIT_FPS:
            own.climb_fps = -VS_REDUCED_LIMIT_FPS

    elif k == AdvisoryType.RA_DO_NOT_DESCEND:
        # Keep climb OK; prevent -VS
        if own.climb_fps < 0:
            own.climb_fps = 0.0
        if own.climb_fps > VS_REDUCED_LIMIT_FPS:
            own.climb_fps = VS_REDUCED_LIMIT_FPS

    # -------- Maintain Rate (Maintain Climb / Maintain Descend)
    elif k == AdvisoryType.RA_MAINTAIN:
        if own.climb_fps > 0.0:
            own.climb_fps = max(min(own.climb_fps, VS_MAINTAIN_MAX_UP_FPS), VS_CLIMB_MIN_FPS)
        elif own.climb_fps < 0.0:
            own.climb_fps = min(max(own.climb_fps, VS_MAINTAIN_MIN_DOWN_FPS), VS_DESC_MAX_FPS)

    # -------- No RA → optional trimming for manual mode
    else:
        if own.control_mode == "MANUAL" and own.manual_cmd is not None:
            if own.manual_cmd == "CLIMB":
                own.climb_fps = own.climb_fps * 0.7 + (own.target_climb_fps or VS_CLIMB_NOMINAL_FPS) * 0.3
            elif own.manual_cmd == "DESCEND":
                own.climb_fps = own.climb_fps * 0.7 + (own.target_climb_fps or VS_DESC_NOMINAL_FPS) * 0.3
            elif own.manual_cmd == "MAINTAIN":
                own.climb_fps *= 0.9