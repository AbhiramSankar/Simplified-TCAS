from typing import Tuple
from .math_utils import dot, norm
from . import models as M
import config

CROSSING_ALT_FT = 250.0


def closing_tau_and_dcpA(rel_pos_m: Tuple[float, float],
                         rel_vel_mps: Tuple[float, float]) -> Tuple[float, float]:
    v2 = dot(rel_vel_mps, rel_vel_mps)
    if v2 <= 1e-6:
        return float("inf"), norm(rel_pos_m)
    tau = -dot(rel_pos_m, rel_vel_mps) / v2
    d_cpa = norm(
        (
            rel_pos_m[0] + (rel_vel_mps[0] * tau),
            rel_pos_m[1] + (rel_vel_mps[1] * tau),
        )
    )
    return tau, d_cpa


def classify_contact(
    own_alt_ft,
    rel_pos_m,
    rel_vel_mps,
    rel_alt_ft,
    rel_climb_fps,
    prev_state=None,
):
    """
    Classify a single intruder contact into CLEAR / TA / RA_* states.

    Includes:
      - TA envelope (tau / DMOD / ZTHR)
      - RA envelope (tau / DMOD / ZTHR / ALIM)
      - Low-altitude RA inhibition and HMD filtering
      - Preventive RAs (RA_DO_NOT_CLIMB / RA_DO_NOT_DESCEND)
      - RA hysteresis and RA_MAINTAIN
    """
    tau, d_cpa = closing_tau_and_dcpA(rel_pos_m, rel_vel_mps)

    # Relative vertical speed
    rel_vs_fps = rel_climb_fps              # ft/s
    rel_vs_fpm = rel_vs_fps * 60.0          # ft/min

    if abs(rel_vs_fpm) > 1e-3:
        # vertical tau in seconds: |Δh| / |v_rel| (ft / (ft/min)) * 60
        vert_tau = abs(rel_alt_ft) / abs(rel_vs_fpm) * 60.0
    else:
        vert_tau = float("inf")

    # ---- Outer CLEAR gate (very loose) ----
    CLEAR_RANGE_M = 1852 * 13  # ~13 NM
    if (
        d_cpa > CLEAR_RANGE_M
        or tau > 60.0
        or abs(rel_alt_ft) > 4000.0
        or tau < 0.0
    ):
        return (M.AdvisoryType.CLEAR, "Clear (out of range or diverging)")

    # ---- Low-altitude / ground flags ----
    ground = own_alt_ft <= config.GROUND_ALT_FT
    low_alt_total_inhibit = own_alt_ft <= config.RA_TOTAL_INHIBIT_ALT_FT

    # ---- Sensitivity Level thresholds (tau / DMOD / ZTHR / ALIM) ----
    th = config.get_sl_thresholds(own_alt_ft)
    ta_tau = th["ta_tau"]
    ra_tau = th["ra_tau"]
    ta_dmod = th["ta_dmod_m"]
    ra_dmod = th["ra_dmod_m"]
    ta_zthr = th["ta_zthr_ft"]
    ra_zthr = th["ra_zthr_ft"]
    ra_alim = th.get("ra_alim_ft")  # may be None at SLs without RA/ALIM

    # ---- TA envelope ----
    range_ok_ta = (ta_tau is not None and tau <= ta_tau) or (
        ta_dmod is not None and d_cpa <= ta_dmod
    )

    vert_ok_ta = (ta_tau is not None and vert_tau <= ta_tau) or (
        abs(rel_alt_ft) <= ta_zthr
    )

    is_ta = range_ok_ta and vert_ok_ta

    # ---- ALIM-based predicted vertical miss ----
    predicted_miss_ft = None
    if ra_tau is not None and ra_alim is not None:
        # Linear prediction: Δh(t) = Δh(0) + v_rel * t
        predicted = rel_alt_ft + rel_vs_fps * ra_tau
        predicted_miss_ft = abs(predicted)

    # ---- RA envelope (before HMD, before low-alt inhibit) ----
    if ra_tau is not None and ra_dmod is not None and ra_zthr is not None:
        range_ok_ra = (tau <= ra_tau) or (d_cpa <= ra_dmod)

        alim_violation = (
            predicted_miss_ft is not None
            and ra_alim is not None
            and predicted_miss_ft < ra_alim
        )

        vert_ok_ra = (
            (vert_tau <= ra_tau)
            or (abs(rel_alt_ft) <= ra_zthr)
            or alim_violation
        )

        base_is_ra = range_ok_ra and vert_ok_ra
    else:
        base_is_ra = False  # RA inhibited at this SL

    # ---- Low-altitude / ground inhibition for RA ----
    if low_alt_total_inhibit or ground:
        base_is_ra = False

    # ---- Horizontal Miss Distance (HMD) filter ----
    hmd_allows_ra = d_cpa <= config.HMD_RA_M

    is_ra = base_is_ra and hmd_allows_ra

    # Helper: are we currently in ANY RA?
    prev_is_ra = isinstance(prev_state, M.AdvisoryType) and prev_state.name.startswith(
        "RA_"
    )

    # ------------------------------------------------------------------
    # Helper to choose a "base" RA sense from geometry (CLIMB/DESC/CROSS)
    # ------------------------------------------------------------------
    def base_ra_kind() -> M.AdvisoryType:
        if abs(rel_alt_ft) < CROSSING_ALT_FT:
            # Treat nearly same-level as crossing RA
            if rel_alt_ft >= 0:
                return M.AdvisoryType.RA_CROSSING_DESCEND
            else:
                return M.AdvisoryType.RA_CROSSING_CLIMB
        else:
            if rel_alt_ft > 0:
                return M.AdvisoryType.RA_DESCEND
            elif rel_alt_ft < 0:
                return M.AdvisoryType.RA_CLIMB
            else:
                # Exact same altitude: arbitrarily choose climb
                return M.AdvisoryType.RA_CLIMB

    # ------------------------------------------------------------------
    # Helper to choose a *preventive* RA sense from geometry
    # (Do Not Climb / Do Not Descend).
    # ------------------------------------------------------------------
    def preventive_ra_kind() -> M.AdvisoryType:
        if rel_alt_ft > 0:
            # Intruder above → unsafe direction is up → "Do Not Climb"
            return M.AdvisoryType.RA_DO_NOT_CLIMB
        elif rel_alt_ft < 0:
            # Intruder below → unsafe direction is down → "Do Not Descend"
            return M.AdvisoryType.RA_DO_NOT_DESCEND
        else:
            # Exactly same altitude: either preventive sense is arguable;
            # choose Do Not Climb by default.
            return M.AdvisoryType.RA_DO_NOT_CLIMB

    # =========================================================
    # RA HYSTERESIS: if already in RA_*, keep RA until fully
    # clear or inhibited, and refine to INCREASE / REDUCE / CROSS.
    # =========================================================
    if prev_is_ra:
        # Immediate termination when entering low-altitude / ground region
        if low_alt_total_inhibit or ground:
            return (
                M.AdvisoryType.CLEAR,
                "Clear (RA inhibited at low altitude/ground)",
            )

        # Still inside RA envelope and HMD allows RA → refine RA subtype
        if hmd_allows_ra and base_is_ra:
            kind = base_ra_kind()

            # Strengthen / weaken based on tau w.r.t. RA threshold
            if ra_tau is not None:
                if tau < ra_tau / 2.0:
                    # More urgent: Increase RA
                    if "DESCEND" in kind.name:
                        kind = M.AdvisoryType.RA_INCREASE_DESCEND
                    else:
                        kind = M.AdvisoryType.RA_INCREASE_CLIMB
                elif tau > ra_tau * 1.2:
                    # Improving but still in RA envelope: Reduce RA
                    if "DESCEND" in kind.name:
                        kind = M.AdvisoryType.RA_REDUCE_DESCEND
                    else:
                        kind = M.AdvisoryType.RA_REDUCE_CLIMB

            return (
                kind,
                f"{kind.name} (τ={tau:.1f}s d_cpa={d_cpa:.0f} m Δalt={rel_alt_ft:.0f} ft)",
            )

        # HMD says lateral miss distance will be large → end RA early
        if not hmd_allows_ra:
            return (M.AdvisoryType.CLEAR, "Clear of conflict (HMD filter)")

        # At this point: we are NOT in RA envelope anymore (base_is_ra == False)

        # Case 1: also not in TA envelope → fully clear
        if not is_ta:
            return (M.AdvisoryType.CLEAR, "Clear of conflict (RA resolved)")

        # Case 2: TA still true, but RA envelope ended → issue RA_MAINTAIN
        # This is where "Maintain vertical speed, maintain" / "maintain altitude"
        # should happen.
        return (
            M.AdvisoryType.RA_MAINTAIN,
            f"RA_MAINTAIN (TA only; hold VS, τ={tau:.1f}s d_cpa={d_cpa:.0f} m Δalt={rel_alt_ft:.0f} ft)",
        )

    # =========================================================
    # Normal escalation logic (no previous RA)
    # CLEAR / TA → TA / RA / CLEAR
    # =========================================================

    if is_ra:
        # Decide whether this is a "mild" RA case where a preventive
        # RA (Do Not Climb / Do Not Descend) is sufficient.
        use_preventive = False
        if ra_tau is not None and ra_zthr is not None:
            # Heuristic: tau fairly close to RA threshold and vertical
            # separation still moderately large → preventive RA.
            tau_ratio = tau / ra_tau if ra_tau > 0 else 0.0
            alt_ratio = abs(rel_alt_ft) / ra_zthr if ra_zthr > 0 else 0.0

            # Example: inside RA envelope but not yet very urgent
            if 0.8 <= tau_ratio <= 1.2 and alt_ratio >= 0.4:
                use_preventive = True

        if use_preventive:
            kind = preventive_ra_kind()
        else:
            kind = base_ra_kind()

        return (
            kind,
            f"{kind.name} (τ={tau:.1f}s d_cpa={d_cpa:.0f} m Δalt={rel_alt_ft:.0f} ft)",
        )

    if is_ta:
        return (
            M.AdvisoryType.TA,
            f"TA (τ={tau:.1f}s d_cpa={d_cpa:.0f} m Δalt={rel_alt_ft:.0f} ft)",
        )

    return (M.AdvisoryType.CLEAR, "Clear (no conflict)")
