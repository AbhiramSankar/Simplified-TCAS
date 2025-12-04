from typing import Dict, Tuple
from .models import Aircraft

class Tracking:
    """
    Maintains situational awareness per ownship.
    For each ownship returns dictionary of intruders {callsign: (rel_pos_m, rel_vel_mps, rel_alt_ft)}.
    """
    def build_tracks(self, traffic: Dict[str, Aircraft]) -> Dict[str, Dict[str, Tuple]]:
        tracks = {}
        for own_cs, own in traffic.items():
            rels = {}
            for oth_cs, oth in traffic.items():
                if own_cs == oth_cs: 
                    continue
                rel_pos = (oth.pos_m[0] - own.pos_m[0], oth.pos_m[1] - own.pos_m[1])
                rel_vel = (oth.vel_mps[0] - own.vel_mps[0], oth.vel_mps[1] - own.vel_mps[1])
                rel_alt = oth.alt_ft - own.alt_ft
                rel_climb_fps = oth.climb_fps - own.climb_fps

                rels[oth_cs] = (rel_pos, rel_vel, rel_alt, rel_climb_fps)
            tracks[own_cs] = rels
        return tracks
