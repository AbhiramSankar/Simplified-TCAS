import math
import pytest
from hypothesis import given, strategies as st

from tcas.math_utils import dot, norm, add, sub, mul


def test_dot_basic():
    assert dot((1, 2), (3, 4)) == 11
    assert dot((0, 0), (3, 4)) == 0
    assert dot((1, -1), (1, 1)) == 0


def test_norm_basic():
    assert norm((3, 4)) == 5
    assert norm((0, 0)) == 0


def test_add_sub_inverse():
    a = (10.0, -5.0)
    b = (-2.0, 3.0)
    c = add(a, b)
    assert sub(c, b) == a
    assert sub(c, a) == b


def test_scalar_multiplication():
    v = (2.0, -3.0)
    k = 4.0
    mv = mul(v, k)  # <-- vector first, scalar second
    assert mv == (8.0, -12.0)
    # homogeneity of norm
    assert norm(mv) == pytest.approx(abs(k) * norm(v))


@given(
    v=st.tuples(st.floats(-1e3, 1e3), st.floats(-1e3, 1e3)),
    k=st.floats(-100, 100),
)
def test_norm_homogeneous(v, k):
    # norm(k * v) ≈ |k| * norm(v)
    mv = mul(v, k)  # <-- same fix: vector, scalar
    assert norm(mv) == pytest.approx(abs(k) * norm(v), rel=1e-6, abs=1e-6)
