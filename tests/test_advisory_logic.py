import pytest

from tcas.advisory import AdvisoryLogic, apply_command, ra_vertical_direction
from tcas.models import Aircraft, AdvisoryType, Advisory


def make_ownship():
    return Aircraft(
        callsign="OWN",
        pos_m=(0.0, 0.0),
        vel_mps=(0.0, 0.0),
        alt_ft=10000.0,
        climb_fps=0.0,
        color=(255, 255, 255),
    )


def test_ra_vertical_direction_mapping():
    assert ra_vertical_direction(AdvisoryType.RA_CLIMB) == 1
    assert ra_vertical_direction(AdvisoryType.RA_DESCEND) == -1
    assert ra_vertical_direction(AdvisoryType.RA_MAINTAIN) == 0


def test_apply_command_basic_climb():
    own = make_ownship()
    own.advisory = Advisory(kind=AdvisoryType.RA_CLIMB, reason="test")
    apply_command(own, override_manual=False)
    assert own.climb_fps >= 15.0  # should command at least this rate


def test_apply_command_basic_descend():
    own = make_ownship()
    own.advisory = Advisory(kind=AdvisoryType.RA_DESCEND, reason="test")
    apply_command(own, override_manual=False)
    assert own.climb_fps <= -15.0


def test_apply_command_maintain_zero_vs():
    own = make_ownship()
    own.climb_fps = 20.0
    own.advisory = Advisory(kind=AdvisoryType.RA_MAINTAIN, reason="test")
    apply_command(own, override_manual=False)
    assert own.climb_fps == 0.0


def test_manual_override_command():
    own = make_ownship()
    own.control_mode = "MANUAL"
    own.manual_cmd = "CLIMB"
    own.target_climb_fps = 20.0

    # No RA (CLEAR) → pilot override should directly command VS when override_manual=True
    own.advisory = Advisory(kind=AdvisoryType.CLEAR, reason="none")

    apply_command(own, override_manual=True)
    assert own.climb_fps >= 15.0  # should be at least the nominal climb rate
