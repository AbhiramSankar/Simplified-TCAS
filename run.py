import pygame, sys
from sim.world import World
from sim.scenarios import SCENARIOS
import config

def load_scenario(key: str):
    fn = SCENARIOS.get(key, SCENARIOS["1"])
    return fn()

def main():
    pygame.init()
    screen = pygame.display.set_mode((config.SCREEN_W, config.SCREEN_H))
    pygame.display.set_caption("Simplified TCAS")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas,menlo,monospace", 16)

    world = World(load_scenario("1"))

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
                    world.reset(load_scenario("1"))
                elif e.key == pygame.K_1:
                    world.reset(load_scenario("1"))
                elif e.key == pygame.K_2:
                    world.reset(load_scenario("2"))
                elif e.key == pygame.K_3:
                    world.reset(load_scenario("3"))

        world.step(config.DT)

        # Render
        from viz.pygame_app import render
        render(screen, font, world.time_s, world.ac)

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    main()
