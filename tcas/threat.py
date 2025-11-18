from typing import Tuple
from .math_utils import dot, norm
from . import models as M
import config


def closing_tau_and_dcpA(rel_pos_m: Tuple[float, float],
                         rel_vel_mps: Tuple[float, float]) -> Tuple[float, float]:
    v2 = dot(rel_vel_mps, rel_vel_mps)
    if v2 <= 1e-6:
        return float('inf'), norm(rel_pos_m)
    tau = - dot(rel_pos_m, rel_vel_mps) / v2
    d_cpa = norm((rel_pos_m[0] + rel_vel_mps[0] * tau,
                  rel_pos_m[1] + rel_vel_mps[1] * tau))
    return tau, d_cpa


def classify_contact(own_alt_ft,
                     rel_pos_m,
                     rel_vel_mps,
                     rel_alt_ft,
                     prev_state=None) -> Tuple[M.AdvisoryType, str]:
    """
    Classify a single intruder relative to ownship into CLEAR / TA / RA_*.

    State evolution:
        CLEAR → TA → RA → CLEAR
    (no RA → TA → CLEAR).

    Enhancements:
      - Sensitivity levels (SL-dependent tau/DMOD/ZTHR)
      - Horizontal Miss Distance (HMD) RA filter
      - Low-altitude / ground RA inhibition:
          * All RAs inhibited below ~1000 ft AGL
          * No RAs when ownship is 'on ground' (~< 50 ft)
    """

    tau, d_cpa = closing_tau_and_dcpA(rel_pos_m, rel_vel_mps)

    # ---- Outer CLEAR gate (very loose) ----
    CLEAR_RANGE_M = 1852 * 13  # ~13 NM
    if (
        d_cpa > CLEAR_RANGE_M
        or tau > 60.0
        or abs(rel_alt_ft) > 4000
        or tau < 0
    ):
        return (M.AdvisoryType.CLEAR, "Clear (out of range or diverging)")

    # ---- Low-altitude / ground flags ----
    ground = own_alt_ft <= config.GROUND_ALT_FT
    low_alt_total_inhibit = own_alt_ft <= config.RA_TOTAL_INHIBIT_ALT_FT

    # ---- Sensitivity Level thresholds (tau / DMOD / ZTHR) ----
    th = config.get_sl_thresholds(own_alt_ft)
    ta_tau   = th["ta_tau"]
    ra_tau   = th["ra_tau"]      # may be None (RA inhibited at low alt)
    ta_dmod  = th["ta_dmod_m"]
    ra_dmod  = th["ra_dmod_m"]
    ta_zthr  = th["ta_zthr_ft"]
    ra_zthr  = th["ra_zthr_ft"]

    # ---- TA envelope ----
    is_ta = (
        (ta_tau is not None and tau < ta_tau) and
        (ta_dmod is not None and d_cpa < ta_dmod) and
        abs(rel_alt_ft) < ta_zthr
    )

    # ---- RA envelope (before HMD, before low-alt inhibit) ----
    if ra_tau is not None and ra_dmod is not None and ra_zthr is not None:
        base_is_ra = (
            (tau < ra_tau or d_cpa < ra_dmod) and
            abs(rel_alt_ft) < ra_zthr
        )
    else:
        base_is_ra = False  # RA inhibited for this SL

    # ---- Low-altitude / ground inhibition for RA ----
    # Below ~1000 ft or on ground, we do not consider any RA.
    if low_alt_total_inhibit or ground:
        base_is_ra = False

    # ---- Horizontal Miss Distance (HMD) filter ----
    hmd_allows_ra = d_cpa <= config.HMD_RA_M

    # For escalation decisions (no previous RA), RA must satisfy both
    # base RA envelope and HMD filter.
    is_ra = base_is_ra and hmd_allows_ra

    # =========================================================
    # RA HYSTERESIS: once RA, stay RA until fully clear OR
    # until HMD / low-alt / ground logic terminates it.
    # =========================================================
    if prev_state in (
        M.AdvisoryType.RA_CLIMB,
        M.AdvisoryType.RA_DESCEND,
        M.AdvisoryType.RA_MAINTAIN,
    ):
        # If we've descended into the low-altitude / ground region,
        # immediately terminate any active RA.
        if low_alt_total_inhibit or ground:
            return (M.AdvisoryType.CLEAR, "Clear (RA inhibited at low altitude/ground)")

        # Still inside RA envelope and HMD allows RA → keep same RA
        if hmd_allows_ra and base_is_ra:
            return (prev_state, "Maintain RA (still in RA envelope)")

        # HMD says horizontal miss distance will be large → end RA early
        if not hmd_allows_ra:
            return (M.AdvisoryType.CLEAR, "Clear of conflict (HMD filter)")

        # No RA envelope and no TA envelope → fully clear
        if (not base_is_ra) and (not is_ta):
            return (M.AdvisoryType.CLEAR, "Clear of conflict (RA resolved)")

        # TA may still be true, but we do NOT downgrade RA → TA.
        return (prev_state, "Maintain RA until conflict fully clear")

    # =========================================================
    # Normal escalation logic (no previous RA)
    # CLEAR / TA → TA / RA / CLEAR
    # =========================================================
    if is_ra:
        if rel_alt_ft > 0:
            return (
                M.AdvisoryType.RA_DESCEND,
                f"RA: DESCEND (τ={tau:.1f}s d_cpa={d_cpa:.0f} m Δalt=+{rel_alt_ft:.0f} ft)",
            )
        elif rel_alt_ft < 0:
            return (
                M.AdvisoryType.RA_CLIMB,
                f"RA: CLIMB (τ={tau:.1f}s d_cpa={d_cpa:.0f} m Δalt={rel_alt_ft:.0f} ft)",
            )
        else:
            return (
                M.AdvisoryType.RA_MAINTAIN,
                f"RA: MAINTAIN (τ={tau:.1f}s d_cpa={d_cpa:.0f} m)",
            )

    if is_ta:
        return (
            M.AdvisoryType.TA,
            f"TA (τ={tau:.1f}s d_cpa={d_cpa:.0f} m Δalt={rel_alt_ft:.0f} ft)",
        )

    return (M.AdvisoryType.CLEAR, "Clear (no conflict)")
