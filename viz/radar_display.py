import pygame, math
import config
from tcas.models import Aircraft, AdvisoryType
from .colors import WHITE, AMBER, RED, CYAN

def draw_range_rings(screen, center, max_nm=12, rings=4):
    radius_px = 1852 * max_nm / (1852 / config.PIXELS_PER_NM)
    step = radius_px / rings
    for i in range(1, rings + 1):
        pygame.draw.circle(screen, (60, 60, 60), center, int(i * step), 1)

def draw_ownship(screen, center):
    pts = [
        (center[0], center[1] - 10),
        (center[0] - 6, center[1] + 8),
        (center[0] + 6, center[1] + 8)
    ]
    pygame.draw.polygon(screen, (255, 255, 255), pts)

def draw_intruder(screen, font, own: Aircraft, intr: Aircraft, center):
    cx, cy = center
    # relative displacement (convert meters to pixels)
    dx = intr.pos_m[0] - own.pos_m[0]
    dy = intr.pos_m[1] - own.pos_m[1]
    distance_m = math.hypot(dx, dy)
    max_range_m = 1852 * 12        # 12 NM in metres
    if distance_m > max_range_m:
        return
    x = cx + dx / (1852 / config.PIXELS_PER_NM)
    y = cy - dy / (1852 / config.PIXELS_PER_NM)

    # determine altitude tag (two-digit hundreds)
    diff = intr.alt_ft - own.alt_ft
    hundreds = int(diff / 100)
    tag = ""
    if abs(diff) <= 1200:
        tag = f"{hundreds:+03d}"
        if intr.climb_fps > 2:
            tag += "↑"
        elif intr.climb_fps < -2:
            tag += "↓"


    # determine advisory type and draw appropriate symbol
    adv = intr.advisory.kind
    proximate = abs(diff) <= 1200
    size = 8

    if adv in (AdvisoryType.RA_CLIMB, AdvisoryType.RA_DESCEND, AdvisoryType.RA_MAINTAIN):
        # Resolution Advisory — filled red square
        pygame.draw.rect(screen, RED, pygame.Rect(x - size, y - size, size * 2, size * 2))
        color = RED
    elif adv == AdvisoryType.TA:
        # Traffic Advisory — filled amber circle
        pygame.draw.circle(screen, AMBER, (x, y), size)
        color = AMBER
    elif proximate:
        # Proximate Traffic — filled white diamond
        pts = [(x, y - size), (x + size, y), (x, y + size), (x - size, y)]
        pygame.draw.polygon(screen, WHITE, pts)
        color = WHITE
    else:
        # Other Traffic — unfilled white diamond
        pts = [(x, y - size), (x + size, y), (x, y + size), (x - size, y)]
        pygame.draw.polygon(screen, WHITE, pts, 2)
        color = WHITE

    # altitude label
    text = font.render(tag, True, color)
    screen.blit(text, (x + 10, y - 8))
    
def draw_radar(screen, font, own: Aircraft, traffic):
    # shift radar left — center it in the left 70% of the screen
    center_x = int(config.SCREEN_W * 0.35)
    center_y = config.SCREEN_H // 2
    center = (center_x, center_y)

    # black radar background
    radius = min(center_x, center_y) - 40
    pygame.draw.circle(screen, (0, 0, 0), center, radius)
    pygame.draw.circle(screen, (100, 100, 100), center, radius, 2)

    # range rings
    def draw_range_rings(center, max_nm=12, rings=4):
        radius_px = 1852 * max_nm / (1852 / config.PIXELS_PER_NM)
        step = radius_px / rings
        for i in range(1, rings + 1):
            pygame.draw.circle(screen, (60, 60, 60), center, int(i * step), 1)
    draw_range_rings(center, max_nm=12, rings=4)

    # heading ticks
    for deg in range(0, 360, 30):
        rad = math.radians(deg)
        r1 = radius - 10
        r2 = radius
        x1 = center_x + r1 * math.sin(rad)
        y1 = center_y - r1 * math.cos(rad)
        x2 = center_x + r2 * math.sin(rad)
        y2 = center_y - r2 * math.cos(rad)
        pygame.draw.line(screen, (100, 100, 100), (x1, y1), (x2, y2), 1)

    # ownship triangle
    pts = [(center_x, center_y - 10),
           (center_x - 6, center_y + 8),
           (center_x + 6, center_y + 8)]
    pygame.draw.polygon(screen, (255, 255, 255), pts)

    # draw each intruder relative to the new radar center
    for intr in traffic.values():
        if intr.callsign == own.callsign:
            continue
        draw_intruder(screen, font, own, intr, center)

    
    # range label
    label = font.render("12 NM", True, WHITE)
    screen.blit(label, (center_x - 20, center_y - radius + 10))
