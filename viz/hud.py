import pygame
from typing import Dict
from tcas.models import Aircraft, AdvisoryType
from .colors import WHITE, AMBER, RED, GREEN

def draw_hud(screen, font, t: float, aircraft: Dict[str, Aircraft]):
    y = 8
    info = [
        f"t = {t:6.1f}s   [1/2/3] scenario  [SPACE] pause  [R] reload  [ESC] quit"
    ]
    for line in info:
        surf = font.render(line, True, WHITE); screen.blit(surf, (8, y)); y += 18

    for cs, ac in aircraft.items():
        if ac.advisory.kind in (AdvisoryType.RA_CLIMB, AdvisoryType.RA_DESCEND, AdvisoryType.RA_MAINTAIN):
            color = RED
        elif ac.advisory.kind == AdvisoryType.TA:
            color = AMBER
        elif ac.advisory.kind == AdvisoryType.CLEAR:
            color = GREEN
        else:
            color = WHITE
        txt = f"{cs}: {ac.advisory.kind.name:10s}  {ac.advisory.reason}"
        surf = font.render(txt, True, color)
        screen.blit(surf, (8, y)); y += 18

