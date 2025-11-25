from __future__ import annotations
from typing import Dict, Tuple
import csv
import os
import random

from tcas.models import Aircraft, Advisory, AdvisoryType
from tcas.advisory import AdvisoryLogic, apply_command
from tcas.sensing import Sensing
from tcas.tracking import Tracking
from tcas.monitor import NMACMonitor
import config

# --- Helpers for coordinated vertical RAs ---------------------------------

# Classify RA kinds by vertical direction
UP_RAS = {
    AdvisoryType.RA_CLIMB,
    getattr(AdvisoryType, "RA_INCREASE_CLIMB", AdvisoryType.RA_CLIMB),
    getattr(AdvisoryType, "RA_CROSSING_CLIMB", AdvisoryType.RA_CLIMB),
    getattr(AdvisoryType, "RA_DO_NOT_DESCEND", AdvisoryType.RA_CLIMB),  # upward sense
}
DOWN_RAS = {
    AdvisoryType.RA_DESCEND,
    getattr(AdvisoryType, "RA_INCREASE_DESCEND", AdvisoryType.RA_DESCEND),
    getattr(AdvisoryType, "RA_CROSSING_DESCEND", AdvisoryType.RA_DESCEND),
    getattr(AdvisoryType, "RA_DO_NOT_CLIMB", AdvisoryType.RA_DESCEND),  # downward sense
}
NEUTRAL_RAS = {
    AdvisoryType.RA_MAINTAIN,
    getattr(AdvisoryType, "RA_REDUCE_CLIMB", AdvisoryType.RA_MAINTAIN),
    getattr(AdvisoryType, "RA_REDUCE_DESCEND", AdvisoryType.RA_MAINTAIN),
}


def ra_vertical_direction(kind: AdvisoryType) -> int:
    """Return +1 (up), -1 (down), or 0 (neutral) for a given RA kind."""
    if kind in UP_RAS:
        return +1
    if kind in DOWN_RAS:
        return -1
    if kind in NEUTRAL_RAS:
        return 0
    return 0


# Map an RA to its "coordinated opposite" vertical sense.
# For any types not present in AdvisoryType, getattr()/hasattr guards keep this safe.
RA_FLIP_MAP: dict[AdvisoryType, AdvisoryType] = {}

if hasattr(AdvisoryType, "RA_CLIMB") and hasattr(AdvisoryType, "RA_DESCEND"):
    RA_FLIP_MAP[AdvisoryType.RA_CLIMB] = AdvisoryType.RA_DESCEND
    RA_FLIP_MAP[AdvisoryType.RA_DESCEND] = AdvisoryType.RA_CLIMB

if hasattr(AdvisoryType, "RA_INCREASE_CLIMB") and hasattr(AdvisoryType, "RA_INCREASE_DESCEND"):
    RA_FLIP_MAP[AdvisoryType.RA_INCREASE_CLIMB] = AdvisoryType.RA_INCREASE_DESCEND
    RA_FLIP_MAP[AdvisoryType.RA_INCREASE_DESCEND] = AdvisoryType.RA_INCREASE_CLIMB

if hasattr(AdvisoryType, "RA_REDUCE_CLIMB") and hasattr(AdvisoryType, "RA_REDUCE_DESCEND"):
    RA_FLIP_MAP[AdvisoryType.RA_REDUCE_CLIMB] = AdvisoryType.RA_REDUCE_DESCEND
    RA_FLIP_MAP[AdvisoryType.RA_REDUCE_DESCEND] = AdvisoryType.RA_REDUCE_CLIMB

if hasattr(AdvisoryType, "RA_CROSSING_CLIMB") and hasattr(AdvisoryType, "RA_CROSSING_DESCEND"):
    RA_FLIP_MAP[AdvisoryType.RA_CROSSING_CLIMB] = AdvisoryType.RA_CROSSING_DESCEND
    RA_FLIP_MAP[AdvisoryType.RA_CROSSING_DESCEND] = AdvisoryType.RA_CROSSING_CLIMB
    
if hasattr(AdvisoryType, "RA_DO_NOT_CLIMB") and hasattr(AdvisoryType, "RA_DO_NOT_DESCEND"):
    RA_FLIP_MAP[AdvisoryType.RA_DO_NOT_CLIMB] = AdvisoryType.RA_DO_NOT_DESCEND
    RA_FLIP_MAP[AdvisoryType.RA_DO_NOT_DESCEND] = AdvisoryType.RA_DO_NOT_CLIMB



class World:
    def __init__(self, aircraft: Dict[str, Aircraft], log_path: str | None = "logs/tcas_log.csv", scenario_name=None) -> None:
        
        for cs, ac in aircraft.items():
            # Bad altitude scenario
            if cs == "INTR_BADALT":
                ac.alt_bias_ft = random.uniform(-800.0, 800.0)
                ac.alt_ft += ac.alt_bias_ft
                print(f"[BAD ALT] {cs}: bias={ac.alt_bias_ft:.1f} ft   sensed={ac.alt_ft:.1f}")

            # Bad vertical rate scenario
            if cs == "INTR_BADVS":
                ac.climb_bias_fps = random.uniform(-10.0, 10.0)   # ~±600 fpm
                ac.climb_fps += ac.climb_bias_fps
                print(f"[BAD VS]  {cs}: bias={ac.climb_bias_fps:.2f} fps   sensed={ac.climb_fps:.2f}")
        
        self.ac: Dict[str, Aircraft] = aircraft
        self.sensing = Sensing()
        self.tracking = Tracking()
        self.logic = AdvisoryLogic()
        self.monitor = NMACMonitor()

        self.time_s: float = 0.0
        self.paused: bool = False

        # manual override used by HUD / controls
        self.manual_override: bool = False

        # --- Logging setup ---
        self.log_path = log_path
        self.log_file = None
        self.log_writer: csv.writer | None = None

        if self.log_path is not None:
            # Ensure directory exists
            log_dir = os.path.dirname(self.log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)

            self.log_file = open(self.log_path, "w", newline="", encoding="utf-8")
            self.log_writer = csv.writer(self.log_file)

            # Header: one row per ownship–intruder pair per timestep
            self.log_writer.writerow([
                "time_s",
                "own_id",
                "intr_id",
                "rel_x_m",
                "rel_y_m",

                # relative altitude (sensed vs true)
                "rel_alt_sensed_ft",
                "rel_alt_true_ft",

                # tau / dCPA (still based on geometry)
                "tau_s",
                "d_cpa_m",

                "advisory",
                "is_nmac",

                # ownship altitude & VS (sensed vs true)
                "own_alt_sensed_ft",
                "own_alt_true_ft",
                "own_climb_sensed_fps",
                "own_climb_true_fps",

                # intruder altitude & VS (sensed vs true)
                "intr_alt_sensed_ft",
                "intr_alt_true_ft",
                "intr_climb_sensed_fps",
                "intr_climb_true_fps",
            ])


    def step(self, dt: float) -> None:
        if self.paused:
            return

        # --- 1) Integrate aircraft motion ---
        for ac in self.ac.values():
            ac.step(dt)

        # --- 2) Build sensing + tracks ---
        picture = self.sensing.snapshot(self.ac)
        rels_by_own = self.tracking.build_tracks(picture)

        # --- 3) Compute advisory for each ownship (no control yet) ---
        for own_id, own in self.ac.items():
            rels = rels_by_own.get(own_id, {})
            # Decide advisory (uses SL/HMD/low-alt logic in classify_contact)
            own.advisory = self.logic.step(own, rels)

        # --- 4) Coordinate vertical RAs between TCAS-equipped pairs ---
        self._coordinate_vertical_ras()

        # --- 5) Apply TCAS/manual command and log metrics ---
        for own_id, own in self.ac.items():
            rels = rels_by_own.get(own_id, {})

            # Apply TCAS/manual command to ownship
            apply_command(own, override_manual=self.manual_override)

            # Logging + NMAC metrics per intruder
            if self.log_writer is not None:
                for intr_id, (rel_pos, rel_vel, rel_alt_ft) in rels.items():
                    # biased values (what TCAS uses)
                    own = self.ac[own_id]
                    intr = self.ac[intr_id]

                    # sensed values (what TCAS uses)
                    own_alt_sensed = own.alt_ft
                    intr_alt_sensed = intr.alt_ft
                    own_climb_sensed = own.climb_fps
                    intr_climb_sensed = intr.climb_fps

                    # biases
                    own_alt_bias = getattr(own, "alt_bias_ft", 0.0)
                    intr_alt_bias = getattr(intr, "alt_bias_ft", 0.0)
                    own_vs_bias = getattr(own, "climb_bias_fps", 0.0)
                    intr_vs_bias = getattr(intr, "climb_bias_fps", 0.0)

                    # true values (updated continuously every step)
                    own_alt_true = own_alt_sensed - own_alt_bias
                    intr_alt_true = intr_alt_sensed - intr_alt_bias
                    rel_alt_true = intr_alt_true - own_alt_true

                    own_climb_true = own_climb_sensed - own_vs_bias
                    intr_climb_true = intr_climb_sensed - intr_vs_bias

                    # NMAC & metrics based on TRUE geometry
                    horiz_m, vert_ft, tau, d_cpa, is_nmac = self.monitor.compute_metrics(
                        rel_pos,
                        rel_vel,
                        rel_alt_true
                    )

                    # Write row
                    self.log_writer.writerow([
                        f"{self.time_s:.2f}",
                        own_id,
                        intr_id,
                        f"{rel_pos[0]:.1f}",
                        f"{rel_pos[1]:.1f}",

                        f"{rel_alt_ft:.1f}",        # sensed
                        f"{rel_alt_true:.1f}",      # true

                        f"{tau:.2f}",
                        f"{d_cpa:.1f}",
                        own.advisory.kind.name,
                        1 if is_nmac else 0,

                        f"{own_alt_sensed:.1f}",
                        f"{own_alt_true:.1f}",
                        f"{own_climb_sensed:.2f}",
                        f"{own_climb_true:.2f}",

                        f"{intr_alt_sensed:.1f}",
                        f"{intr_alt_true:.1f}",
                        f"{intr_climb_sensed:.2f}",
                        f"{intr_climb_true:.2f}",
                    ])


        self.time_s += dt

    def _coordinate_vertical_ras(self) -> None:
        """Enforce coordinated vertical RAs between TCAS-equipped aircraft.

        If two aircraft both have an RA and both advisories command the same
        vertical direction (both up or both down), flip the RA for one
        aircraft so that the pair becomes complementary.
        """
        ids = list(self.ac.keys())
        n = len(ids)

        for i in range(n):
            for j in range(i + 1, n):
                own_id = ids[i]
                intr_id = ids[j]
                a = self.ac[own_id]
                b = self.ac[intr_id]

                # Only coordinate TCAS-equipped, airborne aircraft
                if not (a.tcas_equipped and b.tcas_equipped):
                    continue
                if a.on_ground or b.on_ground:
                    continue

                ka = a.advisory.kind
                kb = b.advisory.kind

                # Only care about RA_* kinds
                if not (ka.name.startswith("RA_") and kb.name.startswith("RA_")):
                    continue

                dir_a = ra_vertical_direction(ka)
                dir_b = ra_vertical_direction(kb)

                # If either is neutral or directions are opposite, leave as-is
                if dir_a == 0 or dir_b == 0:
                    continue
                if dir_a * dir_b < 0:
                    # one up, one down: already coordinated
                    continue

                # At this point: dir_a == dir_b == +1 or == -1 (both up or both down)
                # Choose which aircraft to flip: e.g., the higher one takes the opposite sense.
                if a.alt_ft >= b.alt_ft:
                    flip_target = a
                else:
                    flip_target = b

                old_kind = flip_target.advisory.kind
                new_kind = RA_FLIP_MAP.get(old_kind)

                if new_kind is not None:
                    flip_target.advisory = Advisory(
                        kind=new_kind,
                        reason=flip_target.advisory.reason + " [coordinated vertical RA flip]"
                    )

    def close(self) -> None:
        """Call this when the simulation ends to flush/close the log file."""
        if self.log_file is not None:
            self.log_file.close()
            self.log_file = None
            self.log_writer = None
