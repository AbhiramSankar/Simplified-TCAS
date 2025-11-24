import pygame, math, time
import config
from tcas.models import Aircraft, AdvisoryType
from .colors import WHITE, AMBER, RED, CYAN, GREEN
import threading
import queue


# Flash control state
flash_state = False
last_flash_time = 0
last_advisory = None
last_speech_time = 0
last_loop_time = 0  # for repeating callouts

tts_queue = queue.Queue()


def get_aural_annunciation(prev: str | None, curr: str) -> str | None:
    """
    Map advisory transitions to TCAS II v7.1–style aural annunciations,
    using explicit RA subtypes.
    """
    if prev is None:
        prev = "NONE"

    prev = prev.upper()
    curr = curr.upper()

    ra_states = {n for n in AdvisoryType.__members__ if n.startswith("RA_")}

    # --- Traffic Advisory ---
    if curr == "TA" and prev != "TA":
        return "Traffic, traffic"

    # --- RA Removed / Clear of conflict ---
    if curr == "CLEAR" and prev in ra_states:
        return "Clear of conflict"

    # --- Preventive RA (no change in VS) ---
    if curr == "RA_MAINTAIN" and prev in {"CLEAR", "TA", "NONE"}:
        return "Monitor vertical speed"

    # --- Basic Climb / Descend RAs ---
    if curr == "RA_CLIMB" and prev not in {"RA_CLIMB", "RA_INCREASE_CLIMB"}:
        return "Climb, climb"
    if curr == "RA_DESCEND" and prev not in {"RA_DESCEND", "RA_INCREASE_DESCEND"}:
        return "Descend, descend"

    # --- Altitude Crossing RAs ---
    if curr == "RA_CROSSING_CLIMB":
        return "Climb, crossing climb"
    if curr == "RA_CROSSING_DESCEND":
        return "Descend, crossing descend"

    # --- Increase Climb / Increase Descent RAs ---
    if curr == "RA_INCREASE_CLIMB":
        return "Increase climb, increase climb"
    if curr == "RA_INCREASE_DESCEND":
        return "Increase descent, increase descent"

    # --- Reduce Climb / Reduce Descent RAs (Level off) ---
    if curr in {"RA_REDUCE_CLIMB", "RA_REDUCE_DESCEND"}:
        return "Level off, level off"

    # --- Maintain Rate RA after active RA ---
    if curr == "RA_MAINTAIN" and prev in {
        "RA_CLIMB", "RA_DESCEND",
        "RA_INCREASE_CLIMB", "RA_INCREASE_DESCEND",
        "RA_CROSSING_CLIMB", "RA_CROSSING_DESCEND",
    }:
        return "Maintain vertical speed, maintain"

    # --- RA Reversals ---
    if prev in {"RA_DESCEND", "RA_INCREASE_DESCEND", "RA_CROSSING_DESCEND"} and curr in {
        "RA_CLIMB", "RA_INCREASE_CLIMB", "RA_CROSSING_CLIMB"
    }:
        return "Climb, climb NOW"

    if prev in {"RA_CLIMB", "RA_INCREASE_CLIMB", "RA_CROSSING_CLIMB"} and curr in {
        "RA_DESCEND", "RA_INCREASE_DESCEND", "RA_CROSSING_DESCEND"
    }:
        return "Descend, descend NOW"

    return None

def get_state_loop_phrase(curr: str) -> str | None:
    """
    Phrase to repeat while an advisory remains active.
    Used to loop audio until CLEAR.
    """
    curr = curr.upper()
    if curr == "TA":
        return "Traffic, traffic"
    if curr == "RA_CLIMB":
        return "Climb, climb"
    if curr == "RA_DESCEND":
        return "Descend, descend"
    if curr == "RA_MAINTAIN":
        return "Monitor vertical speed"
    return None  # CLEAR or unknown → no loop

def tts_worker():
    import pyttsx3
    engine = pyttsx3.init()
    engine.setProperty("rate", 180)
    engine.setProperty("volume", 1.0)
    while True:
        text = tts_queue.get()
        if text is None:
            break
        engine.say('<pitch middle="5">'+text+'</pitch>')
        engine.runAndWait()
        tts_queue.task_done()

threading.Thread(target=tts_worker, daemon=True).start()

def speak_async(text):
    tts_queue.put(text)

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

    if adv in (AdvisoryType.RA_CLIMB, AdvisoryType.RA_DESCEND, AdvisoryType.RA_MAINTAIN, AdvisoryType.RA_CROSSING_CLIMB, AdvisoryType.RA_CROSSING_DESCEND, AdvisoryType.RA_INCREASE_CLIMB, AdvisoryType.RA_INCREASE_DESCEND, AdvisoryType.RA_REDUCE_CLIMB, AdvisoryType.RA_REDUCE_DESCEND):
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
    """Draw flashing alert box below radar (in lower section) and play TCAS aural."""
    global flash_state, last_flash_time, last_advisory, last_speech_time, last_loop_time
    now = time.time()
    flash_interval = 0.5        # seconds between toggles
    clear_interval = 2.0        # how long CLEAR flashes once
    loop_interval = 4.0         # repeat RA/TA callouts every 4 s while active

    # Map advisory kind → short label + color for the box
    advisories_map = {
        "CLEAR":               ("CLEAR", GREEN),
        "TA":                  ("TRAFFIC", AMBER),
        "RA_CLIMB":            ("CLIMB", RED),
        "RA_DESCEND":          ("DESCEND", RED),
        "RA_MAINTAIN":         ("MAINTAIN VS", RED),
        "RA_INCREASE_CLIMB":   ("INCREASE CLIMB", RED),
        "RA_INCREASE_DESCEND": ("INCREASE DESCENT", RED),
        "RA_REDUCE_CLIMB":     ("REDUCE CLIMB", RED),
        "RA_REDUCE_DESCEND":   ("REDUCE DESCENT", RED),
        "RA_CROSSING_CLIMB":   ("XING CLIMB", RED),
        "RA_CROSSING_DESCEND": ("XING DESCENT", RED),
    }

    current = advisory_text.upper()
    display_text, color = advisories_map.get(current, ("CLEAR", WHITE))

    # --- Transition-based aural (table-style) ---
    if last_advisory != current:
        phrase = get_aural_annunciation(last_advisory, current)
        if phrase is not None:
            speak_async(phrase)
            last_speech_time = now
            # If we just announced CLEAR OF CONFLICT, we *do not* loop it.

    # --- Looping while advisory remains active (no looping of CLEAR) ---
    if current != "CLEAR":
        loop_phrase = get_state_loop_phrase(current)
        if loop_phrase is not None and (now - last_loop_time) > loop_interval:
            speak_async(loop_phrase)
            last_loop_time = now

    # --- Flash control ---
    if current != "CLEAR":
        # Normal flashing for TA/RA
        if now - last_flash_time > flash_interval:
            flash_state = not flash_state
            last_flash_time = now
    else:
        # Only flash once when switching INTO CLEAR
        if last_advisory and last_advisory != "CLEAR":
            last_flash_time = now
            flash_state = True
        # Keep light on for clear_interval after transition, then stop
        if flash_state and (now - last_flash_time) > clear_interval:
            flash_state = False

    # Remember current advisory for next frame
    last_advisory = current

    # --- Draw box below radar ---
    screen_w, screen_h = screen.get_size()
    box_w, box_h = 350, 70
    box_x = radar_rect.centerx - box_w // 2
    box_y = radar_rect.bottom + 20  # 20px gap below radar

    if box_y + box_h > screen_h:
        box_y = screen_h - box_h - 10

    rect = pygame.Rect(box_x, box_y, box_w, box_h)
    box_color = color if flash_state else (40, 40, 40)

    pygame.draw.rect(screen, box_color, rect, border_radius=10)


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
