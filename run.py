import pygame, sys, argparse, os
from sim.world import World
from sim.scenarios import SCENARIOS
import config
from tcas.io import load_from_csv, load_adsb_with_ownship
from viz.pygame_app import render
from viz.hud import draw_hud


def load_scenario(key: str):
    fn = SCENARIOS.get(key, SCENARIOS["1"])
    return fn()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ownship",
        help="ADS-B CSV file for ownship (if using ADS-B style inputs)",
        default=None,
    )
    parser.add_argument(
        "--input", "-i",
        help="CSV file with aircraft to load OR folder of ADS-B intruder CSVs",
        default=None,
    )
    parser.add_argument(
        "--scenario", "-s",
        help="scenario key (1/2/3) if no input CSV",
        default="1",
    )
    args = parser.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((config.SCREEN_W, config.SCREEN_H))
    pygame.display.set_caption("Simplified TCAS")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas,menlo,monospace", 16)

        # ---- Initial load: either ADS-B ownship+folder, or single CSV, or scenario ----
    if args.input:
        try:
            if args.ownship and os.path.isdir(args.input):
                # Ownship CSV + intruder folder (ADS-B-style)
                ac = load_adsb_with_ownship(args.ownship, args.input)
            elif os.path.isdir(args.input):
                # Folder given but no ownship file
                raise RuntimeError("For ADS-B folders, please also provide --ownship")
            else:
                # Original single-file Cartesian CSV
                ac = load_from_csv(args.input)
        except Exception as e:
            print("Failed to load CSV:", e)
            ac = load_scenario(args.scenario)
    else:
        ac = load_scenario(args.scenario)

    # ------------------------------------------------------------
    # DETECT SCENARIOS & APPLY BIAS (bad altitude or bad VS)
    # ------------------------------------------------------------

    import random

    scenario_name = None

    for cs, aircraft in ac.items():

        # -------- Bad altitude scenario --------
        if cs == "INTR_BADALT":
            scenario_name = "INTR_BADALT"

            # Save TRUE altitude
            aircraft.true_alt_ft = aircraft.alt_ft

            # Random altitude bias (positive or negative)
            bias_ft = random.uniform(-800.0, 800.0)
            aircraft.alt_ft = aircraft.alt_ft + bias_ft
            aircraft.alt_ft += aircraft.alt_bias_ft
            print(f"[BAD ALT] {cs}: bias={bias_ft:.1f} ft "
                  f"(true={aircraft.true_alt_ft:.1f}, sensed={aircraft.alt_ft:.1f})")

        # -------- Bad vertical speed scenario --------
        if cs == "INTR_BADVS":
            scenario_name = "INTR_BADVS"

            # Save TRUE climb rate
            aircraft.true_climb_fps = aircraft.climb_fps

            # Random climb bias (ft/s), ±10 ft/s = ±600 fpm
            bias_fps = random.uniform(-20.0, 20.0)
            aircraft.climb_fps = aircraft.climb_fps + bias_fps
            aircraft.climb_fps += aircraft.climb_bias_fps
            print(f"[BAD VS] {cs}: bias={bias_fps:.2f} ft/s "
                  f"(true={aircraft.true_climb_fps:.2f}, sensed={aircraft.climb_fps:.2f})")

    # ------------------------------------------------------------
    # Create world with scenario name
    # ------------------------------------------------------------
    world = World(ac, scenario_name=scenario_name)


    # UI state
    selected_idx = 0
    callsigns = list(world.ac.keys())
    selected = callsigns[selected_idx] if callsigns else None

    running = True
    while running:
        dt = clock.tick(int(1.0 / config.DT)) / 1000.0
        dt *= config.SPEED_MULTIPLIER

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False

                elif e.key == pygame.K_SPACE:
                    world.paused = not world.paused

                elif e.key == pygame.K_r:
                    # Reload scenario or CSV using same logic as at startup
                    if args.input:
                        try:
                            if args.ownship and os.path.isdir(args.input):
                                ac = load_adsb_with_ownship(args.ownship, args.input)
                            elif os.path.isdir(args.input):
                                raise RuntimeError("For ADS-B folders, please also provide --ownship")
                            else:
                                ac = load_from_csv(args.input)
                        except Exception as ex:
                            print("Failed to reload CSV:", ex)
                            ac = load_scenario(args.scenario)
                    else:
                        ac = load_scenario(args.scenario)

                    world.reset(ac)
                    callsigns = list(world.ac.keys())
                    selected_idx = 0
                    selected = callsigns[selected_idx] if callsigns else None

                elif e.key == pygame.K_1:
                    world.reset(load_scenario("1"))
                    callsigns = list(world.ac.keys())
                    selected_idx = 0
                    selected = callsigns[selected_idx] if callsigns else None

                elif e.key == pygame.K_2:
                    world.reset(load_scenario("2"))
                    callsigns = list(world.ac.keys())
                    selected_idx = 0
                    selected = callsigns[selected_idx] if callsigns else None

                elif e.key == pygame.K_3:
                    world.reset(load_scenario("3"))
                    callsigns = list(world.ac.keys())
                    selected_idx = 0
                    selected = callsigns[selected_idx] if callsigns else None

                # --- Selection & manual control ---
                elif e.key == pygame.K_TAB:
                    callsigns = list(world.ac.keys())
                    if not callsigns:
                        selected = None
                    else:
                        selected_idx = (selected_idx + 1) % len(callsigns)
                        selected = callsigns[selected_idx]

                elif e.key == pygame.K_m:
                    # toggle manual mode for selected aircraft
                    if selected:
                        ac_sel = world.ac[selected]
                        ac_sel.control_mode = "MANUAL" if ac_sel.control_mode != "MANUAL" else "AUTO"
                        if ac_sel.control_mode == "AUTO":
                            ac_sel.manual_cmd = None
                            ac_sel.target_climb_fps = None

                elif e.key == pygame.K_o:
                    # toggle manual override flag in world (global)
                    world.manual_override = not world.manual_override

                elif e.key == pygame.K_c:
                    # clear manual command for selected aircraft
                    if selected:
                        ac_sel = world.ac[selected]
                        ac_sel.manual_cmd = None
                        ac_sel.target_climb_fps = None

                elif e.key == pygame.K_UP:
                    # increase pilot climb request (if MANUAL)
                    if selected:
                        ac_sel = world.ac[selected]
                        if ac_sel.control_mode != "MANUAL":
                            ac_sel.control_mode = "MANUAL"
                        ac_sel.manual_cmd = "CLIMB"
                        ac_sel.target_climb_fps = (ac_sel.target_climb_fps or 10.0) + 5.0

                elif e.key == pygame.K_DOWN:
                    # increase descent request (more negative)
                    if selected:
                        ac_sel = world.ac[selected]
                        if ac_sel.control_mode != "MANUAL":
                            ac_sel.control_mode = "MANUAL"
                        ac_sel.manual_cmd = "DESCEND"
                        ac_sel.target_climb_fps = (ac_sel.target_climb_fps or -10.0) - 5.0

                elif e.key == pygame.K_SPACE and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    # Shift+Space: MAINTAIN for selected
                    if selected:
                        ac_sel = world.ac[selected]
                        ac_sel.control_mode = "MANUAL"
                        ac_sel.manual_cmd = "MAINTAIN"
                        ac_sel.target_climb_fps = 0.0

        # world step
        world.step(config.DT)

        # Render radar + HUD
        render(screen, font, world.time_s, world.ac)
        draw_hud(screen, font, world.time_s, world.ac,
                 selected=selected, manual_override=world.manual_override)

        pygame.display.flip()

    if hasattr(world, "close"):
        world.close()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
