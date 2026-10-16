"""Pygame visualizer."""

import sys
from collections import Counter

import pygame

from FlyIn.models.connections import canonical
from FlyIn.models.graph import Graph
from FlyIn.models.zone_type import ZoneType


class PygameVisualizer:
    def __init__(self, graph: Graph) -> None:
        pygame.init()
        self.graph = graph
        self.screen = pygame.display.set_mode((1920, 1200))
        pygame.display.set_caption("FlyIn - Drone Simulation")
        self.font = pygame.font.SysFont(None, 18)
        self.clock = pygame.time.Clock()
        self.turn = 0
        # where drone were at the previous render (to see which links it used)
        self._where: dict[str, str] = {}
        # Convert map coordinates to screen coordinates.
        xs = [h.x for h in graph.hubs.values()]
        ys = [h.y for h in graph.hubs.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        def scale(value: float, low: float, high: float, size: float) -> float:
            """Determine the box of the map"""

            # prevent division by 0
            if low == high:
                return size // 2
            return 140 + (value - low) * (size - 280) / (high - low)

        self.positions = {
            name: (
                int(scale(h.x, min_x, max_x, 1920)),
                int(scale(h.y, min_y, max_y, 1200)),
            )
            for name, h in graph.hubs.items()
        }
        self.hub_radius = 40

    def render(
        self,
        turn: int,
        occupancy: dict[str, set[str]],
        movement_line: str,
        in_transit: dict[tuple[str, str], int],
    ) -> None:
        """Rendering method.

        Args:
            turn: turn number
            occupancy: drone ids per hub
            in_transit: drone count per connection
            movement_line: unused but kept for TextVisualizer
        """

        self.turn = turn
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        # Connections crossed this turn: drones that changed hub since the
        # previous render (drones still travelling are in `in_transit`).
        where = {d: hub for hub, ds in occupancy.items() for d in ds}
        crossed: Counter[tuple[str, str]] = Counter()
        for drone, hub in where.items():
            before = self._where.get(drone)
            if before is not None and before != hub:
                crossed[canonical(before, hub)] += 1
        self._where = where

        self.screen.fill((245, 247, 250))

        # Draw connections.
        for conn in self.graph.connections.values():
            a = self.positions[conn.zone_a]
            b = self.positions[conn.zone_b]
            pygame.draw.line(self.screen, (170, 180, 190), a, b, 5)

        # Draw hubs and their drone counts.
        for name, hub in self.graph.hubs.items():
            x, y = self.positions[name]
            drones = sorted(occupancy.get(name, set()))
            # start and end hubs are unlimited: no capacity to show
            limited = not (hub.is_start or hub.is_end)
            over = limited and len(drones) > hub.max_drones

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
            ring = (200, 0, 0) if over else (40, 40, 40)
            pygame.draw.circle(self.screen, ring, (x, y), self.hub_radius, 3)

            label = self.font.render(name, True, (20, 20, 20))
            self.screen.blit(
                label, label.get_rect(center=(x, y - self.hub_radius - 20))
            )

            text = str(len(drones))
            if limited:
                text += f"/{hub.max_drones}"
            count = self.font.render(text, True, (255, 255, 255))
            self.screen.blit(count, count.get_rect(center=(x, y)))

            # Show drone IDs below each hub.
            if drones:
                max_per_line = 6
                drone_lines = [
                    drones[i : i + max_per_line]  # noqa: E203
                    for i in range(0, len(drones), max_per_line)
                ]
                y_offset = y + self.hub_radius + 20
                for index, line in enumerate(drone_lines):
                    ids = ", ".join(line)
                    text = self.font.render(ids, True, (30, 30, 30))
                    self.screen.blit(
                        text,
                        text.get_rect(center=(x, y_offset + (index * 15))),
                    )

        # Connection usage, drawn last so the labels stay on top of the hubs.
        placed: list[pygame.Rect] = []
        for conn in self.graph.connections.values():
            a = self.positions[conn.zone_a]
            b = self.positions[conn.zone_b]
            used = crossed[conn.endpoints] + in_transit.get(conn.endpoints, 0)
            cap = conn.max_link_capacity
            color = (200, 0, 0) if used > cap else (20, 20, 20)
            label = self.font.render(f"{used}/{cap}", True, color)
            # Middle of the line first; crossing lines share a middle, so
            # slide along the line if another label is already there.
            for t in (0.5, 0.4, 0.6, 0.3, 0.7):
                center = (
                    int(a[0] + (b[0] - a[0]) * t),
                    int(a[1] + (b[1] - a[1]) * t),
                )
                box = label.get_rect(center=center).inflate(8, 4)
                if not any(box.colliderect(other) for other in placed):
                    break
            placed.append(box)
            pygame.draw.rect(self.screen, (245, 247, 250), box)
            self.screen.blit(label, label.get_rect(center=center))

        title = self.font.render(
            f"Turn: {turn}    In transit: {sum(in_transit.values())}",
            True,
            (20, 20, 20),
        )
        self.screen.blit(title, (30, 20))
        legend = self.font.render(
            "hub: drones/max_drones    connection: used/max_link_capacity"
            "    red = over capacity",
            True,
            (60, 60, 60),
        )
        self.screen.blit(legend, (30, 44))

        pygame.display.flip()
        self.wait_for_input()

        # Pause briefly so each turn is visible.
        deadline = pygame.time.get_ticks() + 500
        while pygame.time.get_ticks() < deadline:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
            self.clock.tick(60)

    def wait_for_input(self) -> None:
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

    def render_initial_state(self, start_hub: str, nb_drones: int) -> None:
        """Display Turn 0 with every drone at the start hub."""

        occupancy: dict[str, set] = {hub: set() for hub in self.graph.hubs}

        for i in range(nb_drones):
            occupancy[start_hub].add(f"D{i + 1}")

        self.render(
            turn=0,
            movement_line="",
            occupancy=occupancy,
            in_transit={},
        )
