"""Minimal text visualizer for the drone simulation.

Prints a summary of each hub's occupancy after every turn.
"""

from .models.graph import Graph

_COLOR_CODES = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "gray": "\033[90m",
}
_RESET = "\033[0m"


def _colorize(text: str, color: str | None) -> str:
    code = _COLOR_CODES.get(color or "", "")
    if not code:
        return text
    return f"{code}{text}{_RESET}"


class TextVisualizer:
    """Prints drone positions as text after each simulation turn."""

    def __init__(self, graph: Graph) -> None:
        """Store a reference to the graph for hub lookups."""
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
            turn: 1-based turn number.
            movement_line: The formatted movement output for this turn.
            occupancy: Current drones per hub.
            in_transit: Current drones per connection (canonical key).
        """
        print(f"--- Turn {turn} ---")
        if movement_line:
            print(movement_line)
        else:
            print("(no moves)")

        for name in sorted(self.graph.hubs):
            drones = occupancy.get(name, set())
            if not drones:
                continue
            drone_list = " ".join(sorted(drones))
            print(f"  {name}: {drone_list}")

        if in_transit:
            for key, count in in_transit.items():
                if count > 0:
                    print(f"  [transit {key[0]}-{key[1]}]: {count} drone(s)")
        print()
