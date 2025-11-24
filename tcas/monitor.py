from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple
import math

import config
from .threat import closing_tau_and_dcpA


@dataclass
class NMACStats:
    """Aggregated statistics for a simulation run."""
    nmac_count: int = 0
    min_horz_m: float = field(default=float("inf"))
    min_vert_ft: float = field(default=float("inf"))

    def record(self, horiz_m: float, vert_ft: float, is_nmac: bool) -> None:
        if horiz_m < self.min_horz_m:
            self.min_horz_m = horiz_m
        if vert_ft < self.min_vert_ft:
            self.min_vert_ft = vert_ft
        if is_nmac:
            self.nmac_count += 1


class NMACMonitor:
    """
    Computes separation metrics and tracks Near Mid-Air Collisions (NMACs).

    For each ownship–intruder pair, we compute:
      - horizontal separation (m)
      - vertical separation (ft)
      - tau (s) and d_cpa (m) via closing_tau_and_dcpA
      - boolean is_nmac
    """

    def __init__(self) -> None:
        self.stats = NMACStats()

    def compute_metrics(
        self,
        rel_pos_m: Tuple[float, float],
        rel_vel_mps: Tuple[float, float],
        rel_alt_ft: float,
    ):
        # Current horizontal + vertical separations
        horiz_m = math.hypot(rel_pos_m[0], rel_pos_m[1])
        vert_ft = abs(rel_alt_ft)

        # Predicted CPA metrics (tau, d_cpa)
        tau, d_cpa = closing_tau_and_dcpA(rel_pos_m, rel_vel_mps)

        # NMAC: both horizontal and vertical thresholds violated
        is_nmac = (
            horiz_m < config.NMAC_HORZ_M
            and vert_ft < config.NMAC_VERT_FT
        )

        # Update cumulative stats
        self.stats.record(horiz_m, vert_ft, is_nmac)

        return horiz_m, vert_ft, tau, d_cpa, is_nmac

    def summary(self) -> NMACStats:
        """Return aggregated NMAC statistics."""
        return self.stats
