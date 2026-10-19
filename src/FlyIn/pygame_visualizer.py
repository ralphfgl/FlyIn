"""Pygame visualizer."""

import sys
from collections import Counter

import pygame

from FlyIn.models.connections import canonical
from FlyIn.models.graph import Graph
from FlyIn.models.zone_type import ZoneType
from FlyIn.color import rgb

WIDTH = 1920
HEIGHT = 1200
# WIDTH = 1180
# HEIGHT = 620


class PygameVisualizer:
    def __init__(self, graph: Graph) -> None:
        pygame.init()
        self.graph = graph
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("FlyIn - Drone Simulation")
        self.font_size = max(12, int(WIDTH * 0.015))
        self.font = pygame.font.SysFont(None, self.font_size)
        self.clock = pygame.time.Clock()
        self.turn = 0
        self._where: dict[str, str] = {}
        xs = [h.x for h in graph.hubs.values()]
        ys = [h.y for h in graph.hubs.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        def scale(value: float, low: float, high: float, size: float) -> float:
            """Determine the box of the map"""

            if low == high:
                return size // 2
            padding = size * 0.15
            return padding + (value - low) * (size - (padding * 2)) / (
                high - low
            )

        self.positions = {
            name: (
                int(scale(h.x, min_x, max_x, WIDTH)),
                int(scale(h.y, min_y, max_y, HEIGHT)),
            )
            for name, h in graph.hubs.items()
        }
        self.hub_radius = max(20, int(min(WIDTH, HEIGHT) * 0.035))

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
        where = {d: hub_name for hub_name, ds in occupancy.items() for d in ds}
        crossed: Counter[tuple[str, str]] = Counter()
        for drone, hub_name in where.items():
            before = self._where.get(drone)
            if before is not None and before != hub_name:
                crossed[canonical(before, hub_name)] += 1
        self._where = where
        self.screen.fill((245, 247, 250))
        for conn in self.graph.connections.values():
            a = self.positions[conn.zone_a]
            b = self.positions[conn.zone_b]
            pygame.draw.line(self.screen, (170, 180, 190), a, b, 5)
        for hub_name, hub in self.graph.hubs.items():
            x, y = self.positions[hub_name]
            drones = sorted(occupancy.get(hub_name, set()))
            limited = not (hub.is_start or hub.is_end)
            over = limited and len(drones) > hub.max_drones
            if hub.color is not None:
                color = rgb(hub.color)
            elif hub.is_start:
                color = rgb("green")
            elif hub.is_end:
                color = rgb("red")
            elif hub.zone_type == ZoneType.RESTRICTED:
                color = rgb("yellow")
            elif hub.zone_type == ZoneType.BLOCKED:
                color = rgb("gray")
            else:
                color = rgb("blue")
            pygame.draw.circle(self.screen, color, (x, y), self.hub_radius)
            ring = (200, 0, 0) if over else (40, 40, 40)
            pygame.draw.circle(self.screen, ring, (x, y), self.hub_radius, 3)
            name_surf = self.font.render(hub_name, True, (20, 20, 20))
            self.screen.blit(
                name_surf,
                name_surf.get_rect(
                    center=(x, y - self.hub_radius - self.font_size)
                ),
            )
            count_text = str(len(drones))
            if limited:
                count_text += f"/{hub.max_drones}"
            count_surf = self.font.render(count_text, True, (255, 255, 255))
            self.screen.blit(count_surf, count_surf.get_rect(center=(x, y)))
            if drones:
                max_per_line = 6
                drone_lines = [
                    drones[i : i + max_per_line]  # noqa: E203
                    for i in range(0, len(drones), max_per_line)
                ]
                y_offset = y + self.hub_radius + self.font_size
                for index, line in enumerate(drone_lines):
                    ids = ", ".join(line)
                    ids_surf = self.font.render(ids, True, (30, 30, 30))
                    self.screen.blit(
                        ids_surf,
                        ids_surf.get_rect(
                            center=(x, y_offset + (index * self.font_size))
                        ),
                    )
        placed: list[pygame.Rect] = []
        for conn in self.graph.connections.values():
            a = self.positions[conn.zone_a]
            b = self.positions[conn.zone_b]
            used = crossed[conn.endpoints] + in_transit.get(conn.endpoints, 0)
            cap = conn.max_link_capacity
            color = (200, 0, 0) if used > cap else (20, 20, 20)
            usage = self.font.render(f"{used}/{cap}", True, color)
            for t in (0.5, 0.4, 0.6, 0.3, 0.7):
                center = (
                    int(a[0] + (b[0] - a[0]) * t),
                    int(a[1] + (b[1] - a[1]) * t),
                )
                box = usage.get_rect(center=center).inflate(8, 4)
                if not any(box.colliderect(other) for other in placed):
                    break
            placed.append(box)
            pygame.draw.rect(self.screen, (245, 247, 250), box)
            self.screen.blit(usage, usage.get_rect(center=center))
        title = self.font.render(f"Turn: {turn}", True, (20, 20, 20))
        self.screen.blit(title, (30, 20))
        pygame.display.flip()
        self.wait_for_input()

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
        """Display turn 0"""

        occupancy: dict[str, set] = {hub: set() for hub in self.graph.hubs}
        for i in range(nb_drones):
            occupancy[start_hub].add(f"D{i + 1}")
        self.render(
            turn=0,
            movement_line="",
            occupancy=occupancy,
            in_transit={},
        )
