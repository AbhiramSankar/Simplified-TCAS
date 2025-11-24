# tests/test_threat_classify_contact.py
import math
import pytest

import config
from tcas.threat import closing_tau_and_dcpA, classify_contact
from tcas.models import AdvisoryType
from hypothesis import given, strategies as st


def test_closing_tau_and_dcpA_far_apart():
    rel_pos = (100_000.0, 0.0)   # 100 km
    rel_vel = (-200.0, 0.0)      # 200 m/s closing
    tau, d_cpa = closing_tau_and_dcpA(rel_pos, rel_vel)

    # tau should be positive and large
    assert tau > 100.0
    assert d_cpa == pytest.approx(0.0, abs=1e-6)


def test_classify_contact_far_clear():
    # Extremely far & safe geometry → CLEAR
    own_alt_ft = 10000.0
    rel_pos = (200_000.0, 0.0)  # very far
    rel_vel = (-50.0, 0.0)      # gentle closing
    rel_alt_ft = 5000.0         # big vertical separation

    kind, reason = classify_contact(
        own_alt_ft=own_alt_ft,
        rel_pos_m=rel_pos,
        rel_vel_mps=rel_vel,
        rel_alt_ft=rel_alt_ft,
        prev_state=None,
    )

    assert kind == AdvisoryType.CLEAR
    assert "Clear" in reason or "clear" in reason


def test_classify_contact_head_on_zero_vertical():
    # Head-on, at same altitude, fairly close: should not be CLEAR.
    own_alt_ft = 10000.0
    rel_pos = (5_000.0, 0.0)    # ~2.7 NM
    rel_vel = (-250.0, 0.0)     # closing
    rel_alt_ft = 0.0

    kind, reason = classify_contact(
        own_alt_ft=own_alt_ft,
        rel_pos_m=rel_pos,
        rel_vel_mps=rel_vel,
        rel_alt_ft=rel_alt_ft,
        prev_state=None,
    )

    # Should be TA or some RA, but not CLEAR.
    assert kind != AdvisoryType.CLEAR
    assert kind in {AdvisoryType.TA} | {
        a for a in AdvisoryType if a.name.startswith("RA_")
    }
    # Optional: just check we at least mention RA/TA logic
    assert "RA_" in reason or "TA" in reason


@given(
    rel_x=st.floats(50_000.0, 500_000.0),
    rel_y=st.floats(50_000.0, 500_000.0),
    rel_alt=st.floats(5_000.0, 50_000.0),
)

def test_classify_contact_property_far_is_clear(rel_x, rel_y, rel_alt):
    kind, _ = classify_contact(
        own_alt_ft=10_000.0,
        rel_pos_m=(rel_x, rel_y),
        rel_vel_mps=(-100.0, 0.0),
        rel_alt_ft=rel_alt,
        prev_state=None,
    )
    assert kind == AdvisoryType.CLEAR