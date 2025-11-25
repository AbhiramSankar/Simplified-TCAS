import random
from typing import Dict
from .models import Aircraft, TrafficPicture

class Sensing:
    def __init__(self, altitude_bias_ft: Dict[str, float] | None = None):
        self.altitude_bias_ft = altitude_bias_ft or {}


    def snapshot(self, world_aircraft: TrafficPicture, dt: float = 1/30) -> TrafficPicture:
        picture: TrafficPicture = {}

        for cs, ac in world_aircraft.items():
            # Clone aircraft for TCAS (so we don't modify true state)
            clone = Aircraft(
                callsign=ac.callsign,
                pos_m=ac.pos_m,
                vel_mps=ac.vel_mps,
                alt_ft=ac.alt_ft,
                climb_fps=ac.climb_fps,
                color=ac.color,
            )
            clone.tcas_equipped = ac.tcas_equipped
            clone.on_ground = ac.on_ground
            clone.advisory = ac.advisory
            clone.control_mode = ac.control_mode
            clone.manual_cmd = ac.manual_cmd
            clone.target_climb_fps = ac.target_climb_fps

            bias = self.altitude_bias_ft.get(cs, 0.0)
            clone.alt_ft = ac.alt_ft + bias

            picture[cs] = clone
        return picture
