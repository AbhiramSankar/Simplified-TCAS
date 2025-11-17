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
    parser.add_argument("--input", "-i", help="CSV file with aircraft to load (overrides scenario)", default=None)
    parser.add_argument("--scenario", "-s", help="scenario key (1/2/3) if no input CSV", default="1")
    args = parser.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((config.SCREEN_W, config.SCREEN_H))
    pygame.display.set_caption("Simplified TCAS")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas,menlo,monospace", 16)

    if args.input:
        try:
            if args.ownship and os.path.isdir(args.input):
                # Ownship CSV + intruder folder
                ac = load_adsb_with_ownship(args.ownship, args.input)
            elif os.path.isdir(args.input):
                # (optional) legacy ADS-B folder loader, or just error
                raise RuntimeError("For ADS-B folders, please also provide --ownship")
            else:
                # Original single-file Cartesian CSV
                ac = load_from_csv(args.input)
        except Exception as e:
            print("Failed to load CSV:", e)
            ac = load_scenario(args.scenario)
    else:
        ac = load_scenario(args.scenario)

    world = World(ac)

    # UI state
    selected_idx = 0
    callsigns = list(world.ac.keys())
    selected = callsigns[selected_idx] if callsigns else None

    running = True
    while running:
        dt = clock.tick(int(1.0/config.DT)) / 1000.0
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
                    # reload scenario or CSV
                    if args.input:
                        world.reset(load_from_csv(args.input))
                    else:
                        world.reset(load_scenario(args.scenario))
                    callsigns = list(world.ac.keys())
                    selected_idx = 0
                    selected = callsigns[selected_idx] if callsigns else None
                elif e.key == pygame.K_1:
                    world.reset(load_scenario("1"))
                    callsigns = list(world.ac.keys()); selected_idx = 0; selected = callsigns[selected_idx] if callsigns else None
                elif e.key == pygame.K_2:
                    world.reset(load_scenario("2"))
                    callsigns = list(world.ac.keys()); selected_idx = 0; selected = callsigns[selected_idx] if callsigns else None
                elif e.key == pygame.K_3:
                    world.reset(load_scenario("3"))
                    callsigns = list(world.ac.keys()); selected_idx = 0; selected = callsigns[selected_idx] if callsigns else None

                # NEW UI interactions
                elif e.key == pygame.K_TAB:
                    # cycle selection
                    callsigns = list(world.ac.keys())
                    if not callsigns:
                        selected = None
                    else:
                        selected_idx = (selected_idx + 1) % len(callsigns)
                        selected = callsigns[selected_idx]

                elif e.key == pygame.K_m:
                    # toggle manual mode for selected aircraft
                    if selected:
                        ac = world.ac[selected]
                        ac.control_mode = "MANUAL" if ac.control_mode != "MANUAL" else "AUTO"
                        if ac.control_mode == "AUTO":
                            # clear manual cmd when going back to auto
                            ac.manual_cmd = None
                            ac.target_climb_fps = None

                elif e.key == pygame.K_o:
                    # toggle manual override flag in world (global)
                    world.manual_override = not world.manual_override

                elif e.key == pygame.K_c:
                    # clear manual command for selected aircraft
                    if selected:
                        ac = world.ac[selected]
                        ac.manual_cmd = None
                        ac.target_climb_fps = None

                elif e.key == pygame.K_UP:
                    # increase pilot climb request (if MANUAL)
                    if selected:
                        ac = world.ac[selected]
                        # If not in MANUAL, enable but keep as soft assist
                        if ac.control_mode != "MANUAL":
                            ac.control_mode = "MANUAL"
                        # set manual command to CLIMB and a modest target (user can press multiple times)
                        ac.manual_cmd = "CLIMB"
                        # increment in steps of 5 ft/s (~300 fpm)
                        ac.target_climb_fps = (ac.target_climb_fps or 10.0) + 5.0

                elif e.key == pygame.K_DOWN:
                    # increase descent request (more negative)
                    if selected:
                        ac = world.ac[selected]
                        if ac.control_mode != "MANUAL":
                            ac.control_mode = "MANUAL"
                        ac.manual_cmd = "DESCEND"
                        ac.target_climb_fps = (ac.target_climb_fps or -10.0) - 5.0

                elif e.key == pygame.K_SPACE and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    # (alternative) Shift+Space to set MAINTAIN for selected
                    if selected:
                        ac = world.ac[selected]
                        ac.control_mode = "MANUAL"
                        ac.manual_cmd = "MAINTAIN"
                        ac.target_climb_fps = 0.0

        # world step
        world.step(config.DT)

        # Render
        render(screen, font, world.time_s, world.ac)
        # draw HUD with selected & override
        draw_hud(screen, font, world.time_s, world.ac, selected=selected, manual_override=world.manual_override)

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    main()
