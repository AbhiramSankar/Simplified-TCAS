import pygame, math, time
import config
from tcas.models import Aircraft, AdvisoryType
from .colors import WHITE, AMBER, RED, CYAN, GREEN
import pyttsx3
import threading

# Flash control state
flash_state = False
last_flash_time = 0
last_advisory = None

# Initialize TTS engine (thread-safe)
tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 180)   # words per minute
tts_engine.setProperty('volume', 2.0)

def speak_async(text):
    """Speak the given text in a background thread."""
    threading.Thread(target=lambda: tts_engine.say('<pitch middle="5">'+text+'</pitch>') or tts_engine.runAndWait(), daemon=True).start()


def draw_intruder(screen, font, own: Aircraft, intr: Aircraft, center):
    cx, cy = center
    dx = intr.pos_m[0] - own.pos_m[0]
    dy = intr.pos_m[1] - own.pos_m[1]
    distance_m = math.hypot(dx, dy)
    max_range_m = 1852 * 12  # 12 NM in metres
    if distance_m > max_range_m:
        return

    # convert to screen coordinates relative to radar center
    x = cx + dx / (1852 / config.PIXELS_PER_NM)
    y = cy - dy / (1852 / config.PIXELS_PER_NM)

    diff = intr.alt_ft - own.alt_ft
    hundreds = int(diff / 100)
    tag = ""
    if abs(diff) <= 1200:
        tag = f"{hundreds:+03d}"
        if intr.climb_fps > 2:
            tag += "↑"
        elif intr.climb_fps < -2:
            tag += "↓"

    # determine advisory type and symbol
    adv = intr.advisory.kind
    proximate = abs(diff) <= 1200
    size = 8
    color = WHITE

    if adv in (AdvisoryType.RA_CLIMB, AdvisoryType.RA_DESCEND, AdvisoryType.RA_MAINTAIN):
        pygame.draw.rect(screen, RED, pygame.Rect(x - size, y - size, size * 2, size * 2))
        color = RED
    elif adv == AdvisoryType.TA:
        pygame.draw.circle(screen, AMBER, (x, y), size)
        color = AMBER
    elif proximate:
        pts = [(x, y - size), (x + size, y), (x, y + size), (x - size, y)]
        pygame.draw.polygon(screen, WHITE, pts)
    else:
        pts = [(x, y - size), (x + size, y), (x, y + size), (x - size, y)]
        pygame.draw.polygon(screen, WHITE, pts, 2)

    # altitude tag
    text = font.render(tag, True, color)
    screen.blit(text, (x + 10, y - 8))


def draw_alert_box(screen, advisory_text, radar_rect):
    """Draw flashing alert box below radar (in lower section)."""
    global flash_state, last_flash_time, last_advisory
    now = time.time()
    flash_interval = 0.5        # seconds between toggles
    clear_interval = 2  # how long CLEAR flashes once


    # choose color
    advisories_map = {
        "CLEAR": ("CLEAR", GREEN),
        "TA": ("TRAFFIC", AMBER),
        "RA_CLIMB": ("CLIMB", RED),
        "RA_DESCEND": ("DESCEND", RED),
        "RA_MAINTAIN": ("MAINTAIN", RED),
    }

    # Normalize input to uppercase to ensure case-insensitive lookup
    display_text, color = advisories_map.get(advisory_text.upper(), ("CLEAR", WHITE))
    
    current = advisory_text.upper()

    # --- Flash Control Logic ---
    # --- Flash control ---
    if current != "CLEAR":
        # Normal flashing for TA/RA
        if now - last_flash_time > flash_interval:
            flash_state = not flash_state
            last_flash_time = now
    else:
        # Only flash once when switching INTO CLEAR
        if last_advisory and last_advisory != "CLEAR":
            # Record transition start once
            last_flash_time = now
            flash_state = True
            speak_async("Clear of conflict")
        # Keep light on for 2 s after transition
        if flash_state and (now - last_flash_time) > clear_interval:
            flash_state = False  # stop after 2 s

    # --- TTS Callouts ---
    if last_advisory != current:
        if current == "TA":
            speak_async("Traffic, traffic")
        elif current == "RA_CLIMB":
            speak_async("Climb, climb")
        elif current == "RA_DESCEND":
            speak_async("Descend, descend")
        elif current == "RA_MAINTAIN":
            speak_async("Maintain vertical speed")
            
    last_advisory = current
    
    screen_w, screen_h = screen.get_size()
    # Radar occupies radar_rect; put box below it
    box_w, box_h = 300, 70
    box_x = radar_rect.centerx - box_w // 2
    box_y = radar_rect.bottom + 20  # 20px gap below radar

    # Adjust if it would exceed screen height
    if box_y + box_h > screen_h:
        box_y = screen_h - box_h - 10

    rect = pygame.Rect(box_x, box_y, box_w, box_h)
    pygame.draw.rect(screen, color if flash_state else (40, 40, 40), rect, border_radius=10)

    font = pygame.font.Font(None, 44)
    text = font.render(display_text.upper(), True, (0, 0, 0))
    text_rect = text.get_rect(center=rect.center)
    screen.blit(text, text_rect)


def draw_radar(screen, font, own: Aircraft, traffic):
    """Split screen: top for radar, bottom for advisory alert box."""
    screen_w, screen_h = screen.get_size()

    # Reserve 80% height for radar, 20% for alert
    radar_h = int(screen_h * 0.90)
    alert_h = screen_h - radar_h

    # Radar centered vertically in top 80%
    center_x = int(screen_w * 0.35)
    center_y = radar_h // 2
    center = (center_x, center_y)
    radius = min(center_x, center_y) - 40

    # radar background
    pygame.draw.circle(screen, (0, 0, 0), center, radius)
    pygame.draw.circle(screen, (100, 100, 100), center, radius, 2)

    # range rings
    for i in range(1, 5):
        pygame.draw.circle(screen, (60, 60, 60), center, int(radius * i / 4), 1)

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

    # intruders
    for intr in traffic.values():
        if intr.callsign == own.callsign:
            continue
        draw_intruder(screen, font, own, intr, center)

    # range label
    label = font.render("12 NM", True, WHITE)
    screen.blit(label, (center_x - 20, center_y - radius + 10))

    # draw alert box in bottom area
    label_text = own.advisory.kind.name if own.advisory else "CLEAR"
    radar_rect = pygame.Rect(center_x - radius, center_y - radius, radius * 2, radius * 2)
    draw_alert_box(screen, label_text, radar_rect)
