import pygame
import textwrap
from typing import Dict
from tcas.models import Aircraft, AdvisoryType
from tcas.threat import closing_tau_and_dcpA   # <-- relative tau/dCPA
import config
from .colors import WHITE, AMBER, RED, GREEN


def draw_hud(screen, font, t: float, aircraft: Dict[str, Aircraft],
             selected: str = None, manual_override: bool = False):
    """Side HUD panel showing controls, advisories, and ownship altitude."""
    screen_w, screen_h = screen.get_size()
    panel_w = int(screen_w * 0.30)
    panel_x = screen_w - panel_w
    margin_x, margin_y = 12, 10
    line_spacing = 20

    # translucent panel
    hud_surface = pygame.Surface((panel_w, screen_h), pygame.SRCALPHA)
    hud_surface.fill((0, 0, 0, 180))
    y = margin_y

    own = list(aircraft.values())[0] if aircraft else None

    # header block
    header_lines = [
        f"t = {t:6.1f}s",
        f"Selected: {selected or 'None'}",
        f"Manual Override: {'ON' if manual_override else 'OFF'}",
        "",
        "Controls:",
        "[1/2/3]  Load scenario",
        "[SPACE]  Pause / Resume",
        "[R]      Reload scenario",
        "[TAB]    Select aircraft",
        "[M]      Toggle manual mode",
        "[O]      Toggle override",
        "[UP/DOWN] Adjust climb/descent",
        "[C]      Clear manual command",
        "",
        "Advisories:",
    ]

    for line in header_lines:
        surf = font.render(line, True, WHITE)
        hud_surface.blit(surf, (margin_x, y))
        y += line_spacing

    # advisory section
    max_text_width = panel_w - 2 * margin_x
    wrap_chars = max_text_width // 9

    for cs, ac in aircraft.items():
        if y > screen_h - line_spacing:
            break

        # Advisory color
        if ac.advisory.kind in (
            AdvisoryType.RA_CLIMB, AdvisoryType.RA_DESCEND,
            AdvisoryType.RA_MAINTAIN,
            AdvisoryType.RA_CROSSING_CLIMB, AdvisoryType.RA_CROSSING_DESCEND,
            AdvisoryType.RA_INCREASE_CLIMB, AdvisoryType.RA_INCREASE_DESCEND,
            AdvisoryType.RA_REDUCE_CLIMB, AdvisoryType.RA_REDUCE_DESCEND,
        ):
            color = RED
        elif ac.advisory.kind == AdvisoryType.TA:
            color = AMBER
        elif ac.advisory.kind == AdvisoryType.CLEAR:
            color = GREEN
        else:
            color = WHITE

        marker = ">" if cs == selected else " "

        # --- Relative metrics vs ownship (for intruders) ---
        rel_info = ""
        if own is not None and cs != own.callsign:
            dx = ac.pos_m[0] - own.pos_m[0]
            dy = ac.pos_m[1] - own.pos_m[1]
            rel_pos = (dx, dy)

            rel_alt_ft = ac.alt_ft - own.alt_ft
            rel_vel = (
                ac.vel_mps[0] - own.vel_mps[0],
                ac.vel_mps[1] - own.vel_mps[1],
            )

            tau, d_cpa_m = closing_tau_and_dcpA(rel_pos, rel_vel)
            d_cpa_nm = d_cpa_m / config.NM_TO_M

            rel_info = (
                f" Δalt={rel_alt_ft:+.0f} ft"
                f" τ={tau:4.1f}s"
                f" dCPA={d_cpa_nm:4.2f} NM"
            )

        # --- Altitude text (sensed + true via bias) ---
        sensed_alt = ac.alt_ft
        alt_bias = getattr(ac, "alt_bias_ft", 0.0)
        true_alt = sensed_alt - alt_bias

        if abs(alt_bias) > 1.0:
            alt_text = f"alt={sensed_alt:.0f} ft (true {true_alt:.0f})"
        else:
            alt_text = f"alt={sensed_alt:.0f} ft"

        # --- Vertical speed text (sensed + true via bias) ---
        sensed_vs_fps = ac.climb_fps
        sensed_vs_fpm = sensed_vs_fps * 60.0
        vs_bias = getattr(ac, "climb_bias_fps", 0.0)
        true_vs_fps = sensed_vs_fps - vs_bias
        true_vs_fpm = true_vs_fps * 60.0

        if abs(vs_bias) > 0.1:
            vs_text = f"VS={sensed_vs_fpm:.0f} fpm (true {true_vs_fpm:.0f})"
        else:
            vs_text = f"VS={sensed_vs_fpm:.0f} fpm"

        base_text = (
            f"{marker}{cs}: {ac.advisory.kind.name}  "
            f"{ac.advisory.reason}  "
            f"{alt_text}  {vs_text}"
            f"{rel_info}  "
            f"mode={ac.control_mode} cmd={ac.manual_cmd or '-'}"
        )

        wrapped = textwrap.wrap(base_text, width=wrap_chars)
        for wline in wrapped:
            if y > screen_h - 2 * line_spacing:
                break
            surf = font.render(wline, True, color)
            hud_surface.blit(surf, (margin_x, y))
            y += line_spacing
        y += 4

    # ownship altitude at bottom right corner
    if aircraft and own is not None:
        own_sensed_alt = own.alt_ft
        own_alt_bias = getattr(own, "alt_bias_ft", 0.0)
        own_true_alt = own_sensed_alt - own_alt_bias

        if abs(own_alt_bias) > 1.0:
            alt_text = (
                f"Own Altitude: {own_sensed_alt:,.0f} ft "
                f"(true {own_true_alt:,.0f})"
            )
        else:
            alt_text = f"Own Altitude: {own_sensed_alt:,.0f} ft"

        surf = font.render(alt_text, True, WHITE)
        hud_surface.blit(surf, (margin_x, screen_h - 2 * line_spacing))

    # border line separating radar and HUD
    pygame.draw.line(hud_surface, (120, 120, 120), (0, 0), (0, screen_h), 1)
    screen.blit(hud_surface, (panel_x, 0))
