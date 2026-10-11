"""Very simple Pygame visualizer for FlyIn."""

import sys

import pygame

from FlyIn.models.graph import Graph
from FlyIn.models.zone_type import ZoneType


class PygameVisualizer:
    def __init__(self, graph: Graph):
        pygame.init()
        self.graph = graph
        # Bigger window: 1920 x 1200
        self.screen = pygame.display.set_mode((1920, 1200))
        pygame.display.set_caption("FlyIn - Drone Simulation")
        self.font = pygame.font.SysFont(None, 18)
        self.clock = pygame.time.Clock()
        self.turn = 0

        # Convert map coordinates to screen coordinates.
        xs = [h.x for h in graph.hubs.values()]
        ys = [h.y for h in graph.hubs.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        def scale(value, low, high, size):
            if low == high:
                return size // 2
            return 140 + (value - low) * (size - 280) / (high - low)

        # Scaled to fill the 1920x1200 window (with margin)
        self.positions = {
            name: (
                int(scale(h.x, min_x, max_x, 1640)),
                int(scale(h.y, min_y, max_y, 1040)),
            )
            for name, h in graph.hubs.items()
        }

        # Hub radius scaled up too
        self.hub_radius = 40

    def render(self, turn, movement_line, occupancy, in_transit):
        self.turn = turn

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        self.screen.fill((245, 247, 250))

        # Draw connections.
        for conn in self.graph.connections.values():
            a = self.positions[conn.zone_a]
            b = self.positions[conn.zone_b]
            pygame.draw.line(self.screen, (170, 180, 190), a, b, 5)

        # Draw hubs and their drone counts.
        for name, hub in self.graph.hubs.items():
            x, y = self.positions[name]

            if hub.is_start:
                color = (70, 180, 100)
            elif hub.is_end:
                color = (230, 90, 90)
            elif hub.zone_type == ZoneType.RESTRICTED:
                color = (240, 170, 50)
            elif hub.zone_type == ZoneType.BLOCKED:
                color = (80, 80, 80)
            else:
                color = (80, 145, 220)

            pygame.draw.circle(self.screen, color, (x, y), self.hub_radius)
            pygame.draw.circle(
                self.screen, (40, 40, 40), (x, y), self.hub_radius, 3
            )

            label = self.font.render(name, True, (20, 20, 20))
            self.screen.blit(
                label, label.get_rect(center=(x, y - self.hub_radius - 20))
            )

            drones = sorted(occupancy.get(name, set()))
            count = self.font.render(str(len(drones)), True, (255, 255, 255))
            self.screen.blit(count, count.get_rect(center=(x, y)))

            # Show drone IDs below each hub.
            if drones:
                ids = ", ".join(drones)
                text = self.font.render(ids, True, (30, 30, 30))
                self.screen.blit(
                    text,
                    text.get_rect(center=(x, y + self.hub_radius + 20)),
                )

        title = self.font.render(
            f"Turn: {turn}    In transit: {sum(in_transit.values())}",
            True,
            (20, 20, 20),
        )
        self.screen.blit(title, (30, 20))

        pygame.display.flip()
        self.wait_for_space()

        # Pause briefly so each turn is visible.
        deadline = pygame.time.get_ticks() + 500
        while pygame.time.get_ticks() < deadline:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
            self.clock.tick(60)

    def wait_for_space(self):
        """Wait until the user presses Space or closes the window."""
        waiting = True

        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit

                if (
                    event.type == pygame.KEYDOWN
                    and event.key == pygame.K_SPACE
                ):
                    waiting = False

            self.clock.tick(30)

    def render_initial_state(self, start_hub, nb_drones):
        """Display Turn 0 with every drone at the start hub."""
        occupancy = {hub: set() for hub in self.graph.hubs}

        for i in range(nb_drones):
            occupancy[start_hub].add(f"D{i + 1}")

        self.render(
            turn=0,
            movement_line="Initial state",
            occupancy=occupancy,
            in_transit={},
        )
