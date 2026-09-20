"""Multi-path discovery from start hub to end."""

import heapq
from dataclasses import dataclass

from .models.graph import Graph
from .models.hub import Hub
from .models.zone_type import ZoneType


@dataclass(frozen=True)
class Path:
    """A candidate route from start to end.
    Attributes:
        hubs: ordered list of hub names (start to end)
        total_cost: sum of movement costs along the path
    """

    hubs: tuple[str, ...]

    @property
    def length(self):
        """Number of edges in the path (hubs -1)."""
        return len(self.hubs) - 1

    # NOTE: ergonomic win (write for hub in path instead of in path.hubs)
    def __iter__(self):
        """Iterate over hub names."""
        return iter(self.hubs)


# a cost is (turn_cost, priority_preference)
# turn cost is the real cost of the move
# priority_preference is a tie breaker (-1 for priority zone, 0 otherwise)
# INF is for blocking zone
_Cost = tuple[int, int]
_INF: _Cost = (10**9, 10**9)


class PathFinder:
    """Discovers multiple distinct-ish path from start to end."""

    def __init__(self, graph: Graph) -> None:
        """Store graph reference and build reusable cost lookup."""
        self.graph = graph
        self._start = graph.start.name
        self._end = graph.end.name
        # penalty multiplier for hubs we already used in prior paths
        self._penalty_factor: float = 2.5

    def find_paths(self, max_paths: int = 6) -> list[Path]:
        """Discover up to max paths distinct routes.
        Args:
            max_paths: upper bound on paths to return.
        Returns:
            A list of Path objects, sorted by ascending total_cost.
        """

        penalties: dict[str, float] = {}
        # dict of path, duplicate collapse automatically
        found: dict[tuple[str, ...], Path] = {}

        for _ in range(max_paths):
            path = self._dijkstra(penalties)
            # unreachable end
            if path is None:
                break
            # store the path
            if path.hubs not in found:
                found[path.hubs] = path
            # penalize internal hubs by +1 (but not start and end)
            for hub_name in path.hubs[1:-1]:
                penalties[hub_name] = penalties.get(hub_name, 0.0) + 1.0

        # sort the discovered path by real cost
        return sorted(found.values(), key=lambda p: self._path_cost(p))

    def _hub_entry_cost(self, hub: Hub, penalties: dict[str, float]) -> _Cost:
        """Return the cost of *entering* the given hub."""

        if not hub.zone_type.is_walkable:
            return _INF
        base = hub.zone_type.movement_cost
        penalty = penalties.get(hub.name, 0.0)
        priority_bonus = -1 if hub.zone_type is ZoneType.PRIORITY else 0
        return (int(base + penalty), priority_bonus)

    def _dijkstra(self, penalties: dict[str, float]) -> Path | None:
        """Run a single cost-weighted Dijkstra search.
        Args:
            penalties: Extra cost added to hub entry, keyed by hub name.
        Returns:
            the best Path found, or None if end is unreachable.
        """

        # dist[hub] = best cumulative cost to reach hub (cheapest way to reach hub from start)
        dist: dict[str, _Cost] = {self._start: (0, 0)}
        # for each hub, which hub we came from on the best path (to reconstruct the route)
        prev: dict[str, str] = {}
        # priority queue, to pick the unknown hub with smallest cost
        heap: list[tuple[_Cost, str]] = [((0, 0), self._start)]
        while heap:
            # pop the cheapest unsettled hub
            cost, current = heapq.heappop(heap)
            # a hub can be pushed to the heap multiple times with decreasing costs (when better route is found); discard a worse entry
            if cost > dist.get(current, _INF):
                continue
            # finish when we pop end
            if current == self._end:
                break
            # for each neighbor, get the cost to enter
            for neighbor_name in self.graph.neighbors(current):
                neighbor = self.graph.hubs[neighbor_name]
                step = self._hub_entry_cost(neighbor, penalties)
                # skip blocked hubs
                if step == _INF:
                    continue
                # compute total cost (current cost + step cost); both component add (cost and priority)
                new_cost = (cost[0] + step[0], cost[1] + step[1])
                # if cheaper than best known, record it and remomeber predecessor
                # push to the heap
                if new_cost < dist.get(neighbor_name, _INF):
                    dist[neighbor_name] = new_cost
                    prev[neighbor_name] = current
                    heapq.heappush(heap, (new_cost, neighbor_name))

        if self._end not in prev and self._start != self._end:
            return None
        # reconstruct path
        path = [self._end]
        while path[-1] != self._start:
            path.append(prev[path[-1]])
        path.reverse()
        # compute realized turn cost along the path
        total = 0
        for hub_name in path[1:]:
            total += self.graph.hubs[hub_name].zone_type.movement_cost
        return Path(hubs=tuple(path))

    def _path_cost(self, path: Path) -> int:
        """Turn cost of a past, ignoring priority tie-break."""
        return sum(
            self.graph.hubs[h].zone_type.movement_cost for h in path.hubs
        )
