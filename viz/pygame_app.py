import pygame
from typing import Dict, Tuple
import config
from tcas.models import Aircraft, AdvisoryType
from .colors import WHITE, CYAN, AMBER, RED, GREY
from .hud import draw_hud
from .radar_display import draw_radar

def world_to_screen(x_m: float, y_m: float) -> Tuple[int,int]:
    # Center origin; +x to right, +y up -> screen y inverted
    sx = int(config.SCREEN_W/2 + x_m / (1852.0/config.PIXELS_PER_NM))
    sy = int(config.SCREEN_H/2 - y_m / (1852.0/config.PIXELS_PER_NM))
    return sx, sy

def draw_aircraft(screen, font, ac: Aircraft):
    x, y = world_to_screen(*ac.pos_m)
    pygame.draw.circle(screen, ac.color, (x, y), 6)
    call = font.render(ac.callsign, True, WHITE)
    screen.blit(call, (x+8, y-8))
    alt = font.render(f"{ac.alt_ft:.0f} ft", True, GREY)
    screen.blit(alt, (x+8, y+6))

def draw_advisory_ring(screen, ac: Aircraft):
    x, y = world_to_screen(*ac.pos_m)
    kind = ac.advisory.kind
    if kind == AdvisoryType.TA:
        color = AMBER
    elif kind in (AdvisoryType.RA_CLIMB, AdvisoryType.RA_DESCEND, AdvisoryType.RA_MAINTAIN):
        color = RED
    else:
        return
    pygame.draw.circle(screen, color, (x, y), 36, 2)

def render(screen, font, time_s, aircraft):
    # find ownship (first aircraft)
    if not aircraft: return
    own = list(aircraft.values())[0]
    traffic = aircraft
    draw_radar(screen, font, own, traffic)
