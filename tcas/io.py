import csv
from typing import Dict
from .models import Aircraft

# CSV columns:
# callsign,x_m,y_m,vel_x_mps,vel_y_mps,alt_ft,climb_fps,color_r,color_g,color_b
# Example:
# OWN001,0,0,150,0,10000,0,200,200,220

def load_from_csv(path: str) -> Dict[str, Aircraft]:
    aircraft = {}
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
                color = (int(row.get('color_r', 200)), int(row.get('color_g',200)), int(row.get('color_b',220)))
            except Exception:
                color = (200,200,220)
            ac = Aircraft(callsign, (x, y), (vx, vy), alt, climb, color=color)
            aircraft[callsign] = ac
    return aircraft

def save_to_csv(path: str, aircraft: Dict[str, Aircraft]):
    import csv
    with open(path, 'w', newline='') as f:
        fieldnames = ['callsign','x_m','y_m','vel_x_mps','vel_y_mps','alt_ft','climb_fps','color_r','color_g','color_b']
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
