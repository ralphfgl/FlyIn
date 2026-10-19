"""Text visualizer for simulation ouput."""

from FlyIn.models.graph import Graph
from FlyIn.color import ansi_fg, ANSI_RESET


class TextVisualizer:
    """Prints drone positions at each sim turns."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    def render(
        self,
        turn: int,
        movement_line: str,
        occupancy: dict[str, set[str]],
        in_transit: dict[tuple[str, str], int],
    ) -> None:
        """Print one turn's state.

        Args:
            occupancy: Current drones per hub.
            in_transit: Current drones per connection (canonical key).
        """
        print(f"--- Turn {turn} ---")
        print(movement_line if movement_line else "(no moves)")
        for name in sorted(self.graph.hubs):
            drones = occupancy.get(name, set())
            if not drones:
                continue
            hub = self.graph.hubs[name]
            col = ansi_fg(hub.color)
            drone_list = " ".join(sorted(drones))
            print(f"  {col}{name}{ANSI_RESET}: {drone_list}")

        if in_transit:
            for key, count in in_transit.items():
                if count > 0:
                    print(f"  [transit {key[0]}-{key[1]}]: {count} drone(s)")
        print()
