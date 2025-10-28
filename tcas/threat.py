from typing import Tuple
from .math_utils import dot, norm
from . import models
from . import models as M
import config

def closing_tau_and_dcpA(rel_pos_m: Tuple[float,float],
                         rel_vel_mps: Tuple[float,float]) -> Tuple[float, float]:
    """
    Time to closest approach (tau) and distance at CPA (d_cpa).
    tau < 0 means past-closest or diverging if rel_vel points outwards.
    """
    v2 = dot(rel_vel_mps, rel_vel_mps)
    if v2 <= 1e-6:
        return float('inf'), norm(rel_pos_m)
    tau = - dot(rel_pos_m, rel_vel_mps) / v2
    d_cpa = norm((rel_pos_m[0] + rel_vel_mps[0]*tau,
                  rel_pos_m[1] + rel_vel_mps[1]*tau))
    return tau, d_cpa

def classify_contact(rel_pos_m, rel_vel_mps, rel_alt_ft) -> Tuple[M.AdvisoryType, str]:
    tau, d_cpa = closing_tau_and_dcpA(rel_pos_m, rel_vel_mps)

    # --- CLEAR / RESET CONDITIONS ---
    CLEAR_RANGE_M = 1852 * 13       # 13 NM (slightly > TA range)
    if (
        d_cpa > CLEAR_RANGE_M           # outside radar scope
        or tau > 60.0                   # time to CPA too long
        or abs(rel_alt_ft) > 4000       # vertical separation large
        or tau < 0                      # diverging
    ):
        return (M.AdvisoryType.CLEAR, "Clear (out of range or diverging)")

    # --- THREAT EVALUATION ---
    # First check TA conditions
    if tau < config.TA_TAU_S and d_cpa < config.TA_HORZ_M and abs(rel_alt_ft) < config.TA_VERT_FT:
        # Escalate to RA if thresholds tighter
        if tau < config.RA_TAU_S and d_cpa < config.RA_HORZ_M and abs(rel_alt_ft) < config.RA_VERT_FT:
            # Resolution Advisory (RA)
            if rel_alt_ft > 0:
                # Intruder above → descend
                return (M.AdvisoryType.RA_DESCEND,
                        f"RA: DESCEND (τ={tau:.1f}s d_cpa={d_cpa:.0f}m rel_alt=+{rel_alt_ft:.0f}ft)")
            elif rel_alt_ft < 0:
                # Intruder below → climb
                return (M.AdvisoryType.RA_CLIMB,
                        f"RA: CLIMB (τ={tau:.1f}s d_cpa={d_cpa:.0f}m rel_alt={rel_alt_ft:.0f}ft)")
            else:
                return (M.AdvisoryType.RA_MAINTAIN,
                        f"RA: MAINTAIN (τ={tau:.1f}s d_cpa={d_cpa:.0f}m)")
        else:
            # Traffic Advisory (TA)
            return (M.AdvisoryType.TA,
                    f"TA (τ={tau:.1f}s d_cpa={d_cpa:.0f}m rel_alt={rel_alt_ft:.0f}ft)")
    # Otherwise clear
    return (M.AdvisoryType.CLEAR, "Clear (no conflict)")

