# Global knobs (simulation + logic thresholds)
SCREEN_W, SCREEN_H = 1200, 800
PIXELS_PER_NM = 25.0        # horizontal scale
FEET_PER_PIXEL = 10.0       # vertical (for display text only)

DT = 1/30.0                 # sim step (s)
SPEED_MULTIPLIER = 1.0

# TCAS thresholds (legacy / fallback)
TA_TAU_S   = 35.0           # if time-to-CPA below -> TA
TA_HORZ_M  = 1200.0         # horizontal CPA alert radius (m)
TA_VERT_FT = 850.0          # vertical sep threshold (ft)

RA_TAU_S   = 25.0
RA_HORZ_M  = 900.0
RA_VERT_FT = 700.0

# Basic climb / descend bias (ft)
MIN_SAFE_VERT_FT = 300.0

# Colors
BG_COLOR = (12, 12, 18)

# How close to 'same altitude' we consider aircraft for RA sense (ft)
RA_DEADBAND_FT = 200.0

# ---------------------------------------------------------------------
# TCAS II–inspired Sensitivity Levels (Table 2, TCAS II v7.1 booklet)
# Each row: (alt_min_ft, alt_max_ft, SL, TA_tau_s, RA_tau_s,
#            TA_DMOD_nm, RA_DMOD_nm, TA_ZTHR_ft, RA_ZTHR_ft)
# RA thresholds can be None where RAs are inhibited (e.g., SL2).
# ---------------------------------------------------------------------

SENSITIVITY_LEVELS = [
    # alt_min, alt_max, SL, TA_tau, RA_tau, TA_DMOD, RA_DMOD, TA_ZTHR, RA_ZTHR
    (0,      1000,   2,  20.0, None,  0.30, None,  850,  None),  # TA-only, RA inhibited
    (1000,   2350,   3,  25.0, 15.0,  0.33, 0.20,  850,  600),
    (2350,   5000,   4,  30.0, 20.0,  0.48, 0.35,  850,  600),
    (5000,   10000,  5,  40.0, 25.0,  0.75, 0.55,  850,  600),
    (10000,  20000,  6,  45.0, 30.0,  1.00, 0.80,  850,  600),
    (20000,  42000,  7,  48.0, 35.0,  1.30, 1.10,  850,  700),
    (42000,  999999, 7,  48.0, 35.0,  1.30, 1.10, 1200,  800),
]

NM_TO_M = 1852.0


def get_sl_thresholds(own_alt_ft: float):
    for (
        amin, amax, sl,
        ta_tau, ra_tau,
        ta_dmod_nm, ra_dmod_nm,
        ta_zthr_ft, ra_zthr_ft,
    ) in SENSITIVITY_LEVELS:
        if amin <= own_alt_ft < amax:
            return {
                "sl": sl,
                "ta_tau": ta_tau,
                "ra_tau": ra_tau,
                "ta_dmod_m": ta_dmod_nm * NM_TO_M if ta_dmod_nm is not None else None,
                "ra_dmod_m": ra_dmod_nm * NM_TO_M if ra_dmod_nm is not None else None,
                "ta_zthr_ft": ta_zthr_ft,
                "ra_zthr_ft": ra_zthr_ft,
            }

    # Fallback: use legacy fixed thresholds
    return {
        "sl": None,
        "ta_tau": TA_TAU_S,
        "ra_tau": RA_TAU_S,
        "ta_dmod_m": TA_HORZ_M,
        "ra_dmod_m": RA_HORZ_M,
        "ta_zthr_ft": TA_VERT_FT,
        "ra_zthr_ft": RA_VERT_FT,
    }


# ---------------------------------------------------------------------
# Horizontal Miss Distance (HMD) filter for RA:
# If predicted horizontal miss distance at CPA is larger than this,
# suppress RA onset and allow early RA termination.
# ~1.3 NM, consistent with TCAS II DMOD/HMD scales for upper SLs.
# ---------------------------------------------------------------------
HMD_RA_M = 1.3 * NM_TO_M

# ---------------------------------------------------------------------
# Low-altitude / ground RA inhibition (simplified DO-185B behavior):
# - Below GROUND_ALT_FT, treat ownship as "on ground" -> no RA.
# - Below RA_TOTAL_INHIBIT_ALT_FT, inhibit all RAs (TA only).
#   This roughly matches "all RAs inhibited below 1000±100 ft AGL". :contentReference[oaicite:3]{index=3}
# ---------------------------------------------------------------------
GROUND_ALT_FT = 50.0          # ~ radar altitude "on ground" threshold
RA_TOTAL_INHIBIT_ALT_FT = 1000.0

# --- NMAC (Near Mid-Air Collision) thresholds ---
# A "safety violation" event if BOTH are true:
#   - horizontal separation < 0.3 NM
#   - vertical separation   < 300 ft
NMAC_HORZ_M = 0.3 * NM_TO_M   # ≈ 556 m
NMAC_VERT_FT = 300.0