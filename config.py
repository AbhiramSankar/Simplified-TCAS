# Global knobs (simulation + logic thresholds)
SCREEN_W, SCREEN_H = 1200, 800
PIXELS_PER_NM = 25.0        # horizontal scale
FEET_PER_PIXEL = 10.0       # vertical (for display text only)

DT = 1/30.0                 # sim step (s)
SPEED_MULTIPLIER = 1.0

# TCAS-ish thresholds (VERY simplified)
TA_TAU_S   = 35.0           # if time-to-CPA below -> TA
TA_HORZ_M  = 1200.0         # horizontal CPA alert radius (m)
TA_VERT_FT = 850.0          # vertical sep threshold (ft)

RA_TAU_S   = 25.0
RA_HORZ_M  = 900.0
RA_VERT_FT = 700.0

# Basic climb / descend bias (ft)
MIN_SAFE_VERT_FT = 300.0

# Colors
BG_COLOR = (12, 12, 18)
