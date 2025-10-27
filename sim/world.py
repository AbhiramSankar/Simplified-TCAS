from typing import Dict
from tcas.models import Aircraft
from tcas.advisory import AdvisoryLogic, apply_command
from tcas.sensing import Sensing
from tcas.tracking import Tracking

class World:
    def __init__(self, aircraft: Dict[str, Aircraft]) -> None:
        self.ac: Dict[str, Aircraft] = aircraft
        self.sensing = Sensing()
        self.tracking = Tracking()
        self.logic = AdvisoryLogic()
        self.time_s = 0.0
        self.paused = False

    def reset(self, aircraft: Dict[str, Aircraft]):
        self.ac = aircraft
        self.time_s = 0.0

    def step(self, dt: float):
        if self.paused:
            return
        # Physics update
        for ac in self.ac.values():
            ac.step(dt)

        # Sensing snapshot → tracking relations
        picture = self.sensing.snapshot(self.ac)
        rels_by_own = self.tracking.build_tracks(picture)

        # Advisory per ownship
        for cs, own in self.ac.items():
            own.advisory = self.logic.step(own, rels_by_own.get(cs, {}))
            apply_command(own)

        self.time_s += dt
