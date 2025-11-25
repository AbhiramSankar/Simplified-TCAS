#!/usr/bin/env python3
"""
TCAS log analysis script.

Reads a tcas_log.csv produced by World/logging and computes:

- Basic counts:
    * Fraction of time spent in CLEAR / TA / RA
    * Number of NMAC samples

- Accuracy metrics vs. a hazard model aligned with TCAS RA envelopes:
    * Hazard is defined using RA tau / DMOD / ZTHR thresholds and HMD,
      via config.get_sl_thresholds() and config.HMD_RA_M.
    * Confusion matrix: TP/TN/FP/FN
    * Accuracy, precision, recall, F1-score

- Timeliness:
    * RA lead time relative to hazard onset
    * RA lead time relative to NMAC (if any)

- Stability:
    * Total number of advisory changes
    * Average changes per ownship
    * Changes per 100 samples
    * Max changes for any ownship (worst chatter)

- Reliability:
    * Hazard “episodes” (per own/intr pair)
    * Successes / failures
    * Reliability ratio

Usage:
    python analysis.py tcas_log.csv
    python analysis.py tcas_log.csv --out-csv summary.csv
"""

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import config  # assumes analysis.py is in same project root as config.py


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
@dataclass
class LogRow:
    time_s: float
    own_id: str
    intr_id: str
    own_alt_ft: float
    rel_x_m: float
    rel_y_m: float
    rel_alt_ft: float
    tau_s: float
    d_cpa_m: float
    advisory: str
    is_nmac: bool


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_log(path: str) -> List[LogRow]:
    """
    Load the TCAS log CSV into a list of LogRow objects, sorted by time.
    """
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
                        own_alt_ft=float(r["own_alt_ft"]),   # NEW
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


# ---------------------------------------------------------------------------
# Utility / classification helpers
# ---------------------------------------------------------------------------

def advisory_level(advisory: str) -> int:
    """
    Map advisory text → severity level.

    0: CLEAR
    1: TA
    2: RA (any "RA_*")
    """
    adv = advisory.upper().strip()
    if adv.startswith("RA_"):
        return 2
    if adv == "TA":
        return 1
    return 0


def compute_hazard_flags(rows: List[LogRow]) -> List[bool]:
    """
    Hazard model aligned with the TCAS RA implementation in threat.py.

    A state is considered "RA-level hazardous" if:

      - The RA envelope is satisfied at this ownship altitude:
            (tau < ra_tau  OR  d_cpa < ra_dmod)
            AND |Δalt| < ra_zthr
      - AND RA is not totally inhibited by low-altitude / ground
      - AND Horizontal Miss Distance (HMD) allows RA:
            d_cpa <= config.HMD_RA_M

    Uses per-row own_alt_ft so SL / inhibit behaviour matches the live logic.
    """
    flags: List[bool] = []

    for r in rows:
        own_alt_ft = r.own_alt_ft

        # Sensitivity-level thresholds at this altitude
        th = config.get_sl_thresholds(own_alt_ft)
        ra_tau  = th["ra_tau"]
        ra_dmod = th["ra_dmod_m"]
        ra_zthr = th["ra_zthr_ft"]

        # Low-altitude / ground inhibition
        ground = own_alt_ft <= config.GROUND_ALT_FT
        low_alt_total_inhibit = own_alt_ft <= config.RA_TOTAL_INHIBIT_ALT_FT

        # If RA not defined or totally inhibited at this SL, no RA-level hazard
        if (
            ra_tau is None
            or ra_dmod is None
            or ra_zthr is None
            or low_alt_total_inhibit
            or ground
        ):
            flags.append(False)
            continue

        # Base geometry
        tau = r.tau_s
        d_cpa = r.d_cpa_m
        rel_alt_ft = r.rel_alt_ft

        # Base RA envelope (same structure as in threat.py)
        base_is_ra = ((tau < ra_tau) or (d_cpa < ra_dmod)) and (abs(rel_alt_ft) < ra_zthr)

        # Horizontal Miss Distance filter
        hmd_allows_ra = d_cpa <= config.HMD_RA_M

        is_ra_env = base_is_ra and hmd_allows_ra
        flags.append(is_ra_env)

    return flags



def group_by_pair(rows: List[LogRow]) -> Dict[Tuple[str, str], List[LogRow]]:
    """
    Group rows by (own_id, intr_id) and sort each sub-sequence by time.
    """
    groups: Dict[Tuple[str, str], List[LogRow]] = defaultdict(list)
    for r in rows:
        groups[(r.own_id, r.intr_id)].append(r)
    for k in groups:
        groups[k].sort(key=lambda x: x.time_s)
    return groups


# ---------------------------------------------------------------------------
# Metric computations
# ---------------------------------------------------------------------------

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

    ra_count = sum(v for k, v in counts.items() if advisory_level(k) == 2)
    ta_count = sum(v for k, v in counts.items() if advisory_level(k) == 1)
    clear_count = sum(v for k, v in counts.items() if advisory_level(k) == 0)

    return {
        "total_samples": total,
        "frac_RA": ra_count / total,
        "frac_TA": ta_count / total,
        "frac_CLEAR": clear_count / total,
        "count_RA": ra_count,
        "count_TA": ta_count,
        "count_CLEAR": clear_count,
        "nmac_samples": nmac_count,
    }


def compute_accuracy(rows: List[LogRow]) -> Dict[str, float]:
    """
    Accuracy based on hazard model that mirrors RA envelopes:

    - Hazard present? (per compute_hazard_flags)
    - Alert issued? (TA or RA)

    TP: hazard and alert
    TN: no hazard and CLEAR
    FP: no hazard but alert (nuisance TA/RA)
    FN: hazard but CLEAR (missed alert)
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

    accuracy = (TP + TN) / total if total else 0.0
    precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
    recall = TP / (TP + FN) if (TP + FN) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    alert_rate = (
        sum(1 for r in rows if advisory_level(r.advisory) >= 1) / total
        if total
        else 0.0
    )
    hazard_rate = sum(1 for h in hazard_flags if h) / total if total else 0.0

    return {
        "accuracy": accuracy,
        "precision_alert": precision,
        "recall_hazard": recall,
        "f1_alert": f1,
        "TP": TP,
        "TN": TN,
        "FP": FP,
        "FN": FN,
        "hazard_rate": hazard_rate,
        "alert_rate": alert_rate,
    }


def compute_timeliness(rows: List[LogRow]) -> Dict[str, float]:
    """
    Timeliness metrics:
    - For each (own,intr) pair, find first hazard onset and first RA issuance.
    - Timeliness = RA_time - hazard_onset_time (positive = late, negative = early).
    - Also compute RA lead time before first NMAC if present.
    """
    groups = group_by_pair(rows)

    lead_times: List[float] = []
    lead_times_nmac: List[float] = []

    for key, seq in groups.items():
        # Hazard per row in this pair using the same hazard model
        h_flags = compute_hazard_flags(seq)

        # Hazard onset
        hazard_onset_time: Optional[float] = None
        for r, h in zip(seq, h_flags):
            if h:
                hazard_onset_time = r.time_s
                break

        # First RA issuance
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
    Stability: how often advisories change over time.

    For each own_id, count the number of advisory changes over time,
    normalized by duration and/or steps.
    """
    by_own: Dict[str, List[LogRow]] = defaultdict(list)
    for r in rows:
        by_own[r.own_id].append(r)

    total_changes = 0
    total_steps = 0
    per_own_changes: Dict[str, int] = {}

    for own_id, seq in by_own.items():
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
    max_changes_any_own = max(per_own_changes.values()) if per_own_changes else 0

    return {
        "total_changes": total_changes,
        "avg_changes_per_own": avg_changes_per_own,
        "changes_per_100_steps": changes_per_100_steps,
        "max_changes_any_own": max_changes_any_own,
        "num_ownships": len(per_own_changes),
    }


def compute_reliability(rows: List[LogRow]) -> Dict[str, float]:
    """
    Reliability: how often hazard episodes are handled without NMAC.

    Approximate definition:
      - A 'hazard episode' is a (own,intr) pair where hazard flag is ever true.
      - Success if no NMAC occurs for that pair (or RA issued before any NMAC).
      - Failure if NMAC occurs and RA was too late or never issued.
    """
    groups = group_by_pair(rows)

    episodes = 0
    successes = 0
    failures = 0

    for key, seq in groups.items():
        h_flags = compute_hazard_flags(seq)
        hazard_any = any(h_flags)
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


# ---------------------------------------------------------------------------
# Main / reporting
# ---------------------------------------------------------------------------

def print_block(title: str, metrics: Dict[str, float]) -> None:
    print(title)
    for k in sorted(metrics.keys()):
        print(f"{k:25s}: {metrics[k]}")
    print()


def write_metrics_csv(path: str, blocks: Dict[str, Dict[str, float]]) -> None:
    """
    Flatten named metric blocks into a single-row CSV for easy comparison
    across runs (e.g., baseline vs fault-injection).
    """
    flat: Dict[str, float] = {}
    for block_name, metrics in blocks.items():
        for k, v in metrics.items():
            flat[f"{block_name}.{k}"] = v

    fieldnames = sorted(flat.keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(flat)


def main():
    parser = argparse.ArgumentParser(description="Analyze TCAS log CSV.")
    parser.add_argument("csv_path", help="Path to tcas_log.csv")
    parser.add_argument(
        "--out-csv",
        help="Optional path to write a single-row CSV summary of all metrics.",
        default=None,
    )
    args = parser.parse_args()

    rows = load_log(args.csv_path)

    basic = compute_basic_counts(rows)
    acc = compute_accuracy(rows)
    timeliness = compute_timeliness(rows)
    stability = compute_stability(rows)
    reliability = compute_reliability(rows)

    print_block("=== Basic Counts ===", basic)
    print_block("=== Accuracy Metrics ===", acc)
    print_block("=== Timeliness Metrics ===", timeliness)
    print_block("=== Stability Metrics ===", stability)
    print_block("=== Reliability Metrics ===", reliability)

    print("Note:")
    print(" - Run this script on multiple logs (baseline vs fault-injection) to assess resilience.")
    print(" - Refine the hazard definition and thresholds in compute_hazard_flags "
          "to match your report more precisely.")
    print()

    if args.out_csv:
        all_blocks = {
            "basic": basic,
            "accuracy": acc,
            "timeliness": timeliness,
            "stability": stability,
            "reliability": reliability,
        }
        write_metrics_csv(args.out_csv, all_blocks)
        print(f"Metric summary written to: {args.out_csv}")


if __name__ == "__main__":
    main()
