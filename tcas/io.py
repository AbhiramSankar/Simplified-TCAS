import csv, math, os
from typing import Dict
from .models import Aircraft

NM_TO_M = 1852.0
KT_TO_MPS = 0.514444
FPM_TO_FPS = 1.0 / 60.0


def _bool_from_int_str(value: str, default: bool = False) -> bool:
    """Helper to parse '0'/'1' (or missing) into bool."""
    if value is None:
        return default
    value = value.strip()
    if value == "":
        return default
    try:
        return bool(int(value))
    except ValueError:
        # fallback: accept 'true'/'false'
        return value.lower() in ("1", "true", "yes", "y")


def load_adsb_with_ownship(ownship_file: str, intruder_folder: str) -> Dict[str, Aircraft]:
    """
    Load one ADS-B-style CSV for ownship and a folder of ADS-B-style CSVs
    for intruders. Ownship is placed at (0,0) with zero horizontal velocity.
    Intruders are positioned using range_nm/bearing_deg relative to ownship.

    Expected columns in each ADS-B CSV:
      time_s,aircraft_id,df,icao24,mode,altitude_ft,vertical_rate_fpm,
      on_ground,tcas_equipped,identity,squawk,range_nm,bearing_deg,range_rate_kt
    """
    aircraft: Dict[str, Aircraft] = {}

    # ---- 1) Read ownship row ----
    with open(ownship_file, newline="") as f:
        reader = csv.DictReader(f)
        own_rows = list(reader)

    if not own_rows:
        raise RuntimeError(f"No rows in ownship file: {ownship_file}")

    own_row = own_rows[0]
    own_id = own_row["aircraft_id"]

    alt_ft = float(own_row["altitude_ft"])
    climb_fps = float(own_row["vertical_rate_fpm"]) * FPM_TO_FPS

    on_ground = _bool_from_int_str(own_row.get("on_ground", "0"), default=False)
    tcas_equipped = _bool_from_int_str(own_row.get("tcas_equipped", "1"), default=True)

    aircraft[own_id] = Aircraft(
        callsign=own_id,
        pos_m=(0.0, 0.0),
        vel_mps=(0.0, 0.0),  # ownship at origin in own frame
        alt_ft=alt_ft,
        climb_fps=climb_fps,
        icao24=own_row.get("icao24"),
        mode=own_row.get("mode"),
        squawk=own_row.get("squawk"),
        identity=own_row.get("identity", own_id),
        on_ground=on_ground,
        tcas_equipped=tcas_equipped,
        color=(255, 255, 255),
    )

    # ---- 2) Read all intruder CSVs from folder ----
    for fname in os.listdir(intruder_folder):
        if not fname.lower().endswith(".csv"):
            continue

        full = os.path.join(intruder_folder, fname)
        with open(full, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ac_id = row["aircraft_id"]
                if ac_id == own_id:
                    # Skip if ownship file was also dropped here
                    continue

                range_nm = float(row["range_nm"])
                bearing_deg = float(row["bearing_deg"])
                range_m = range_nm * NM_TO_M
                bearing_rad = math.radians(bearing_deg)

                # 0° = North, 90° = East; y negative is North (ownship frame)
                x_m = range_m * math.sin(bearing_rad)
                y_m = -range_m * math.cos(bearing_rad)

                # Radial range rate → approx horizontal velocity along LOS
                range_rate_kt = float(row["range_rate_kt"])
                radial_mps = range_rate_kt * KT_TO_MPS
                vx_mps = radial_mps * math.sin(bearing_rad)
                vy_mps = -radial_mps * math.cos(bearing_rad)

                alt_ft = float(row["altitude_ft"])
                climb_fps = float(row["vertical_rate_fpm"]) * FPM_TO_FPS

                on_ground = _bool_from_int_str(row.get("on_ground", "0"), default=False)
                tcas_equipped = _bool_from_int_str(row.get("tcas_equipped", "1"), default=True)

                aircraft[ac_id] = Aircraft(
                    callsign=ac_id,
                    pos_m=(x_m, y_m),
                    vel_mps=(vx_mps, vy_mps),
                    alt_ft=alt_ft,
                    climb_fps=climb_fps,
                    icao24=row.get("icao24"),
                    mode=row.get("mode"),
                    squawk=row.get("squawk"),
                    identity=row.get("identity", ac_id),
                    on_ground=on_ground,
                    tcas_equipped=tcas_equipped,
                    color=(255, 255, 255),
                )

    if len(aircraft) == 1:
        raise RuntimeError("Only ownship loaded; no intruders found.")

    return aircraft


# CSV columns:
# callsign,x_m,y_m,vel_x_mps,vel_y_mps,alt_ft,climb_fps,color_r,color_g,color_b
# Example:
# OWN001,0,0,150,0,10000,0,200,200,220

def load_from_csv(path: str) -> Dict[str, Aircraft]:
    """Load simple Cartesian scenario CSV (legacy) into Aircraft objects."""
    aircraft: Dict[str, Aircraft] = {}
    with open(path, newline='') as f:
        r = csv.DictReader(f)
        for row in r:
            callsign = row['callsign']
            x = float(row.get('x_m', row.get('x', 0)))
            y = float(row.get('y_m', row.get('y', 0)))
            vx = float(row.get('vel_x_mps', row.get('vx', 0)))
            vy = float(row.get('vel_y_mps', row.get('vel_y', 0)))
            alt = float(row.get('alt_ft', 0))
            climb = float(row.get('climb_fps', 0))
            try:
                color = (
                    int(row.get('color_r', 200)),
                    int(row.get('color_g', 200)),
                    int(row.get('color_b', 220)),
                )
            except Exception:
                color = (200, 200, 220)

            ac = Aircraft(
                callsign=callsign,
                pos_m=(x, y),
                vel_mps=(vx, vy),
                alt_ft=alt,
                climb_fps=climb,
                on_ground=False,
                tcas_equipped=True,
                color=color,
            )
            aircraft[callsign] = ac
    return aircraft


def save_to_csv(path: str, aircraft: Dict[str, Aircraft]):
    with open(path, 'w', newline='') as f:
        fieldnames = [
            'callsign', 'x_m', 'y_m', 'vel_x_mps', 'vel_y_mps',
            'alt_ft', 'climb_fps', 'color_r', 'color_g', 'color_b'
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for cs, ac in aircraft.items():
            w.writerow({
                'callsign': cs,
                'x_m': ac.pos_m[0],
                'y_m': ac.pos_m[1],
                'vel_x_mps': ac.vel_mps[0],
                'vel_y_mps': ac.vel_mps[1],
                'alt_ft': ac.alt_ft,
                'climb_fps': ac.climb_fps,
                'color_r': ac.color[0],
                'color_g': ac.color[1],
                'color_b': ac.color[2],
            })
