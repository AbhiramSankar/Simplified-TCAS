import math
import pytest
from hypothesis import given, strategies as st

import config
from tcas.monitor import NMACMonitor


def test_nmac_true_when_within_thresholds():
    mon = NMACMonitor()
    # just inside thresholds
    rel_pos = (config.NMAC_HORZ_M / 2, 0.0)
    rel_vel = (0.0, 0.0)  # doesn't matter for NMAC flag
    rel_alt_ft = config.NMAC_VERT_FT / 2

    horiz_m, vert_ft, tau, d_cpa, is_nmac = mon.compute_metrics(
        rel_pos, rel_vel, rel_alt_ft
    )

    assert horiz_m == pytest.approx(math.hypot(*rel_pos))
    assert vert_ft == pytest.approx(abs(rel_alt_ft))
    assert is_nmac is True
    assert mon.stats.nmac_count == 1


def test_nmac_false_when_outside_horizontal():
    mon = NMACMonitor()
    rel_pos = (config.NMAC_HORZ_M * 2, 0.0)  # well outside
    rel_vel = (0.0, 0.0)
    rel_alt_ft = 0.0

    _, _, _, _, is_nmac = mon.compute_metrics(rel_pos, rel_vel, rel_alt_ft)
    assert is_nmac is False
    assert mon.stats.nmac_count == 0


def test_nmac_false_when_outside_vertical():
    mon = NMACMonitor()
    rel_pos = (0.0, 0.0)
    rel_vel = (0.0, 0.0)
    rel_alt_ft = config.NMAC_VERT_FT * 2  # far vertical

    _, _, _, _, is_nmac = mon.compute_metrics(rel_pos, rel_vel, rel_alt_ft)
    assert is_nmac is False
    assert mon.stats.nmac_count == 0


@given(
    x=st.floats(-1e5, 1e5),
    y=st.floats(-1e5, 1e5),
    z=st.floats(-1e5, 1e5),
)
def test_nmac_property_outside_thresholds_no_nmac(x, y, z):
    """
    Property: if either horizontal or vertical sep is above the configured
    thresholds, NMAC must be False.
    """
    mon = NMACMonitor()

    # force at least one dimension to be clearly outside thresholds
    too_far_horiz = math.hypot(x, y) > config.NMAC_HORZ_M
    too_far_vert = abs(z) > config.NMAC_VERT_FT

    if not (too_far_horiz or too_far_vert):
        # skip cases where both are inside; property only asserts "if outside → no NMAC"
        return

    _, _, _, _, is_nmac = mon.compute_metrics((x, y), (0.0, 0.0), z)
    assert is_nmac is False
