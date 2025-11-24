#!/usr/bin/env python3
"""
TCAS log analysis script.

Reads a tcas_log.csv produced by World/logging and computes:
- Accuracy (TP/TN/FP/FN vs a simple hazard model)
- Timeliness (RA lead time before hazard / NMAC)
- Stability (advisory changes over time)
- Reliability (hazard episodes handled without NMAC)
- Resilience inputs (same metrics; compare between runs)

Usage:
    python analysis.py tcas_log.csv
"""

import csv
import argparse
from collections import defaultdict, Counter
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import config  # assumes analysis.py is in same project root as config.py


@dataclass
class LogRow:
    time_s: float
    own_id: str
    intr_id: str
    rel_x_m: float
    rel_y_m: float
    rel_alt_ft: float
    tau_s: float
    d_cpa_m: float
    advisory: str
    is_nmac: bool


def load_log(path: str) -> List[LogRow]:
    rows: List[LogRow] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                rows.append(
                    LogRow(
                        time_s=float(r["time_s"]),
                        own_id=r["own_id"],
                        intr_id=r["intr_id"],
                        rel_x_m=float(r["rel_x_m"]),
                        rel_y_m=float(r["rel_y_m"]),
                        rel_alt_ft=float(r["rel_alt_ft"]),
                        tau_s=float(r["tau_s"]),
                        d_cpa_m=float(r["d_cpa_m"]),
                        advisory=r["advisory"],
                        is_nmac=(str(r["is_nmac"]).strip() == "1"),
                    )
                )
            except KeyError as e:
                raise RuntimeError(f"Missing expected column in CSV: {e}")
    rows.sort(key=lambda x: x.time_s)
    return rows


def advisory_level(advisory: str) -> int:
    """
    Map advisory text → severity level.

    0: CLEAR
    1: TA
    2: RA (any RA_*)
    """
    adv = advisory.upper()
    if adv.startswith("RA_"):
        return 2
    if adv == "TA":
        return 1
    return 0


def compute_hazard_flags(rows: List[LogRow]) -> List[bool]:
    """
    Simple 'hazard present' flag per row, using config thresholds.

    We call a (own,intr) state a hazard if it is inside RA envelope-ish:
      tau < RA_TAU_S and |Δalt| < RA_VERT_FT.
    (You can tune this if needed to be more/less conservative.)
    """
    flags: List[bool] = []
    for r in rows:
        hazard = (r.tau_s < config.RA_TAU_S) and (abs(r.rel_alt_ft) < config.RA_VERT_FT)
        flags.append(hazard)
    return flags


def compute_accuracy(rows: List[LogRow]) -> Dict[str, float]:
    """
    Accuracy based on a simple binary classification:
    - Hazard present? (per compute_hazard_flags)
    - Alert issued? (TA or RA)

    TP: hazard and alert
    TN: no hazard and CLEAR
    FP: no hazard but alert
    FN: hazard but CLEAR
    """
    hazard_flags = compute_hazard_flags(rows)

    TP = TN = FP = FN = 0
    for r, hazard in zip(rows, hazard_flags):
        level = advisory_level(r.advisory)
        alert = level >= 1  # TA or RA counts as 'alert'

        if hazard and alert:
            TP += 1
        elif not hazard and not alert:
            TN += 1
        elif not hazard and alert:
            FP += 1
        elif hazard and not alert:
            FN += 1

    total = TP + TN + FP + FN
    return {
        "accuracy": (TP + TN) / total if total else 0.0,
        "TP": TP,
        "TN": TN,
        "FP": FP,
        "FN": FN,
    }


def group_by_pair(rows: List[LogRow]) -> Dict[Tuple[str, str], List[LogRow]]:
    groups: Dict[Tuple[str, str], List[LogRow]] = defaultdict(list)
    for r in rows:
        groups[(r.own_id, r.intr_id)].append(r)
    for k in groups:
        groups[k].sort(key=lambda x: x.time_s)
    return groups


def compute_timeliness(rows: List[LogRow]) -> Dict[str, float]:
    """
    Timeliness metrics:
    - For each (own,intr) pair, find first hazard onset and first RA issuance.
    - Timeliness = RA_time - hazard_onset_time (positive = late, negative = early).
    - Also compute RA lead time before first NMAC if present.
    """
    groups = group_by_pair(rows)
    hazard_flags = compute_hazard_flags(rows)
    # Map row index → hazard flag for convenience
    # but we actually need per-pair; recompute per pair below:

    lead_times: List[float] = []
    lead_times_nmac: List[float] = []

    for key, seq in groups.items():
        # compute hazard per row in this pair
        h_flags = [
            (r.tau_s < config.RA_TAU_S) and (abs(r.rel_alt_ft) < config.RA_VERT_FT)
            for r in seq
        ]

        # hazard onset
        hazard_onset_time: Optional[float] = None
        for r, h in zip(seq, h_flags):
            if h:
                hazard_onset_time = r.time_s
                break

        # first RA issuance
        ra_time: Optional[float] = None
        for r in seq:
            if advisory_level(r.advisory) == 2:
                ra_time = r.time_s
                break

        # NMAC time (if any)
        nmac_time: Optional[float] = None
        for r in seq:
            if r.is_nmac:
                nmac_time = r.time_s
                break

        # RA vs hazard onset
        if hazard_onset_time is not None and ra_time is not None:
            lead_times.append(ra_time - hazard_onset_time)

        # RA vs NMAC
        if nmac_time is not None and ra_time is not None:
            lead_times_nmac.append(nmac_time - ra_time)

    def _avg(xs: List[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    return {
        "avg_RA_minus_hazard_s": _avg(lead_times),
        "avg_NMAC_minus_RA_s": _avg(lead_times_nmac),
        "samples_hazard_RA": len(lead_times),
        "samples_RA_NMAC": len(lead_times_nmac),
    }


def compute_stability(rows: List[LogRow]) -> Dict[str, float]:
    """
    Stability: how often advisories change.

    For each own_id, count the number of advisory changes over time,
    normalized by duration and/or steps.
    """
    # group by ownship (ignoring intruder)
    by_own: Dict[str, List[LogRow]] = defaultdict(list)
    for r in rows:
        by_own[r.own_id].append(r)

    total_changes = 0
    total_steps = 0
    per_own_changes: Dict[str, int] = {}

    for own_id, seq in by_own.items():
        # sort by time
        seq.sort(key=lambda x: x.time_s)
        last_adv: Optional[str] = None
        changes = 0
        for r in seq:
            if last_adv is None:
                last_adv = r.advisory
            else:
                if r.advisory != last_adv:
                    changes += 1
                    last_adv = r.advisory
        per_own_changes[own_id] = changes
        total_changes += changes
        total_steps += len(seq)

    avg_changes_per_own = (
        total_changes / len(per_own_changes) if per_own_changes else 0.0
    )
    changes_per_100_steps = (total_changes / total_steps * 100) if total_steps else 0.0

    return {
        "total_changes": total_changes,
        "avg_changes_per_own": avg_changes_per_own,
        "changes_per_100_steps": changes_per_100_steps,
    }


def compute_reliability(rows: List[LogRow]) -> Dict[str, float]:
    """
    Reliability: how often hazard episodes are handled without NMAC.
    Approximate definition:
      - A 'hazard episode' is a (own,intr) pair where hazard flag is ever true.
      - Success if no NMAC occurs for that pair (or RA issued before any NMAC).
      - Failure if NMAC occurs (especially if RA was never issued).
    """
    groups = group_by_pair(rows)

    episodes = 0
    successes = 0
    failures = 0

    for key, seq in groups.items():
        # hazard present?
        hazard_any = any(
            (r.tau_s < config.RA_TAU_S) and (abs(r.rel_alt_ft) < config.RA_VERT_FT)
            for r in seq
        )
        if not hazard_any:
            continue

        episodes += 1
        nmac_time: Optional[float] = None
        ra_time: Optional[float] = None

        for r in seq:
            if r.is_nmac and nmac_time is None:
                nmac_time = r.time_s
            if advisory_level(r.advisory) == 2 and ra_time is None:
                ra_time = r.time_s

        if nmac_time is None:
            # No NMAC at all -> success
            successes += 1
        else:
            # NMAC happened; success if RA preceded it, failure otherwise
            if ra_time is not None and ra_time < nmac_time:
                successes += 1
            else:
                failures += 1

    reliability = successes / episodes if episodes else 0.0
    return {
        "episodes": episodes,
        "successes": successes,
        "failures": failures,
        "reliability": reliability,
    }


def compute_basic_counts(rows: List[LogRow]) -> Dict[str, float]:
    """
    Basic counts: RA/TA/CLEAR proportions and NMAC count.
    """
    counts = Counter()
    nmac_count = 0
    for r in rows:
        counts[r.advisory] += 1
        if r.is_nmac:
            nmac_count += 1

    total = sum(counts.values()) or 1
    frac_ra = sum(v for k, v in counts.items() if advisory_level(k) == 2) / total
    frac_ta = sum(v for k, v in counts.items() if k.upper() == "TA") / total
    frac_clear = counts.get("CLEAR", 0) / total

    return {
        "total_samples": total,
        "frac_RA": frac_ra,
        "frac_TA": frac_ta,
        "frac_CLEAR": frac_clear,
        "nmac_samples": nmac_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze TCAS log CSV.")
    parser.add_argument("csv_path", help="Path to tcas_log.csv")
    args = parser.parse_args()

    rows = load_log(args.csv_path)

    basic = compute_basic_counts(rows)
    acc = compute_accuracy(rows)
    timeliness = compute_timeliness(rows)
    stability = compute_stability(rows)
    reliability = compute_reliability(rows)

    print("=== Basic Counts ===")
    for k, v in basic.items():
        print(f"{k:25s}: {v}")

    print("\n=== Accuracy Metrics ===")
    for k, v in acc.items():
        print(f"{k:25s}: {v}")

    print("\n=== Timeliness Metrics ===")
    for k, v in timeliness.items():
        print(f"{k:25s}: {v}")

    print("\n=== Stability Metrics ===")
    for k, v in stability.items():
        print(f"{k:25s}: {v}")

    print("\n=== Reliability Metrics ===")
    for k, v in reliability.items():
        print(f"{k:25s}: {v}")

    print("\nNote:")
    print(" - Run this script on multiple logs (baseline vs fault-injection) to assess resilience.")
    print(" - You can refine the hazard definition and thresholds in compute_hazard_flags "
          "to match your report more precisely.")


if __name__ == "__main__":
    main()
