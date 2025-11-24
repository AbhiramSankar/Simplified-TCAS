import pytest

import config
from tcas.threat import classify_contact
from tcas.models import AdvisoryType


def _is_ra(kind: AdvisoryType) -> bool:
    return kind.name.startswith("RA_")

def test_ra_hysteresis_does_not_downgrade_to_ta():
    # Choose an altitude that uses SL=6 thresholds (10000–20000 ft)
    own_alt_ra = 15000.0

    rel_pos_ra = (1000.0, 0.0)        # ~0.54 NM
    rel_vel_ra = (-50.0, 0.0)         # closing
    rel_alt_ft_ra = 0.0               # same level

    kind1, reason1 = classify_contact(
        own_alt_ft=own_alt_ra,
        rel_pos_m=rel_pos_ra,
        rel_vel_mps=rel_vel_ra,
        rel_alt_ft=rel_alt_ft_ra,
        prev_state=None,
    )

    assert _is_ra(kind1), f"Expected initial RA, got {kind1} ({reason1})"


    rel_alt_ft_ta_only = 700.0  # 600 < 700 < 850 for SL6

    kind2, reason2 = classify_contact(
        own_alt_ft=own_alt_ra,
        rel_pos_m=rel_pos_ra,
        rel_vel_mps=rel_vel_ra,
        rel_alt_ft=rel_alt_ft_ta_only,
        prev_state=kind1,  # previous RA
    )

    # Hysteresis: should NOT downgrade RA -> TA while TA still true.
    assert _is_ra(kind2), f"Expected RA to be maintained by hysteresis, got {kind2} ({reason2})"
    assert "Maintain RA" in reason2 or "RA_" in reason2


def test_low_altitude_inhibits_ra_onset():
    # Altitude in the TA-only SL (0–1000 ft)
    own_alt_low = min(800.0, config.RA_TOTAL_INHIBIT_ALT_FT - 50.0)

    # Geometry that would clearly be RA at higher altitude:
    rel_pos = (1000.0, 0.0)
    rel_vel = (-50.0, 0.0)
    rel_alt = 0.0

    kind, reason = classify_contact(
        own_alt_ft=own_alt_low,
        rel_pos_m=rel_pos,
        rel_vel_mps=rel_vel,
        rel_alt_ft=rel_alt,
        prev_state=None,
    )

    # At low altitude with total RA inhibit, we must NOT get any RA_*.
    assert not _is_ra(kind), f"RA should be inhibited at low alt, got {kind} ({reason})"
    # Typically TA or CLEAR is okay here.


def test_low_altitude_clears_existing_ra():
    own_alt_high = 15000.0
    rel_pos = (1000.0, 0.0)
    rel_vel = (-50.0, 0.0)
    rel_alt = 0.0

    kind1, reason1 = classify_contact(
        own_alt_ft=own_alt_high,
        rel_pos_m=rel_pos,
        rel_vel_mps=rel_vel,
        rel_alt_ft=rel_alt,
        prev_state=None,
    )
    assert _is_ra(kind1), f"Expected RA at high altitude, got {kind1} ({reason1})"

    own_alt_low = min(800.0, config.RA_TOTAL_INHIBIT_ALT_FT - 50.0)

    kind2, reason2 = classify_contact(
        own_alt_ft=own_alt_low,
        rel_pos_m=rel_pos,
        rel_vel_mps=rel_vel,
        rel_alt_ft=rel_alt,
        prev_state=kind1,
    )

    # Hysteresis block should immediately terminate RA at low altitude.
    assert kind2 == AdvisoryType.CLEAR, f"Expected CLEAR due to low-alt RA inhibit, got {kind2} ({reason2})"
    assert "inhibit" in reason2.lower() or "low altitude" in reason2.lower() or "ground" in reason2.lower()


def test_hmd_filter_ends_ra_when_predicted_miss_is_large():
    own_alt = 15000.0

    rel_pos_ra = (1000.0, 0.0)
    rel_vel_ra = (-50.0, 0.0)
    rel_alt_ra = 0.0

    kind1, reason1 = classify_contact(
        own_alt_ft=own_alt,
        rel_pos_m=rel_pos_ra,
        rel_vel_mps=rel_vel_ra,
        rel_alt_ft=rel_alt_ra,
        prev_state=None,
    )
    assert _is_ra(kind1), f"Expected initial RA, got {kind1} ({reason1})"

    big_lateral_m = config.HMD_RA_M * 1.5  # well beyond HMD threshold
    rel_pos_hmd = (0.0, big_lateral_m)
    rel_vel_hmd = (-50.0, 0.0)  # dot(rel_pos, rel_vel) = 0 -> tau ~ 0
    rel_alt_hmd = 0.0

    kind2, reason2 = classify_contact(
        own_alt_ft=own_alt,
        rel_pos_m=rel_pos_hmd,
        rel_vel_mps=rel_vel_hmd,
        rel_alt_ft=rel_alt_hmd,
        prev_state=kind1,
    )

    # Expect RA to terminate due to HMD filter
    assert not _is_ra(kind2), f"Expected RA to end due to HMD filter, got {kind2} ({reason2})"
    assert "HMD" in reason2 or "miss distance" in reason2 or "Clear of conflict (HMD" in reason2
