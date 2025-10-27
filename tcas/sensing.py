from typing import Dict
from .models import TrafficPicture, Aircraft

class Sensing:
    """
    In a real system this would ingest Mode S / ADS-B.
    Here it simply snapshots the World state as the 'authoritative' input.
    """
    def snapshot(self, world_aircraft: Dict[str, Aircraft]) -> TrafficPicture:
        # Return shallow copies (safe for read-only downstream)
        return {cs: ac for cs, ac in world_aircraft.items()}
