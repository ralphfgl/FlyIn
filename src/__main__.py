"""Entry point for the Fly-in drone simulation."""

import argparse
import sys

from .parser import ParseError, parse_file, ParsedMap
from .pathfinder import PathFinder
from .scheduler import Scheduler
from .vizualizer import TextVisualizer


def main() -> int:
    """Parse arguments, run the simulation, print the result."""
    parser = argparse.ArgumentParser(description="Fly-in drone router")
    parser.add_argument("map_file", help="Path to the map file")
    parser.add_argument(
        "--max-paths",
        type=int,
        default=6,
        help="Maximum number of paths to discover (default: 6)",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Print hub occupancy after each turn",
    )
    args = parser.parse_args()

    try:
        parsed: ParsedMap = parse_file(args.map_file)
        graph, nb_drones = parsed.graph, parsed.nb_drones
    except ParseError as exc:
        print(f"Parse error: {exc}", file=sys.stderr)
        return 1

    pathfinder = PathFinder(graph)
    paths = pathfinder.find_paths(args.max_paths)
    if not paths:
        print("No path from start to end exists", file=sys.stderr)
        return 1

    visualizer = TextVisualizer(graph) if args.visualize else None
    scheduler = Scheduler(graph, paths, nb_drones, visualizer=visualizer)
    turns = scheduler.run()

    for line in turns:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
