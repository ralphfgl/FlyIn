"""Multi-path discovery from start hub to end."""

import heapq
from typing import Self

from pydantic import (
    BaseModel,
    model_validator,
    ConfigDict,
    Field,
    NonNegativeInt,
)

from FlyIn.models.graph import Graph
from FlyIn.models.hub import Hub
from FlyIn.models.zone_type import ZoneType


class Path(BaseModel):
    """A candidate route from start to end.

    Attributes:
        hubs: ordered list of hub names (start to end)
        step_costs: turns needed to enter each hub (0 for start)
            limited by hub capa and link capa
    """

    model_config = ConfigDict(frozen=True)
    hubs: tuple[str, ...] = Field(min_length=1)
    step_costs: tuple[NonNegativeInt, ...]

    @model_validator(mode="after")
    def _one_cost_each_hub(self) -> Self:
        if len(self.step_costs) != len(self.hubs):
            raise ValueError("step_costs must have on entry per hubs")
        return self

    @property
    def length(self) -> int:
        """Number of edges in the path (hubs -1)."""

        return len(self.hubs) - 1

    @property
    def cost(self) -> int:
        """Turns needed by a drone to fly the path"""

        return sum(self.step_costs)

    @property
    def cost_remaining(self) -> tuple[int, ...]:
        """Nb of turns to reach the end, from each pos"""

        left = [0] * len(self.hubs)
        for i in range(len(self.hubs) - 2, -1, -1):
            left[i] = left[i + 1] + self.step_costs[i + 1]
        return tuple(left)


# Search cost is (turn_cost, priority_preference)
# turn cost is the real cost of the move
# priority_preference is a tie breaker (-1 for priority zone, 0 otherwise)
_Cost = tuple[float, float]
_INF: _Cost = (float("inf"), float("inf"))


class PathFinder:
    """Discovers multiple path from start to end."""

    def __init__(self, graph: Graph) -> None:
        """Store the graph.
        Args:
            graph: the validated network
        """

        self.graph = graph
        self._start = graph.start.name
        self._end = graph.end.name

    def find_paths(self, max_paths: int = 6) -> list[Path]:
        """Discover up to max_paths distinct routes.
        Args:
            max_paths: upper bound on paths to return.
        Returns:
            A list of Path objects, sorted by ascending total_cost.
        """

        penalties: dict[str, float] = {}
        # dict of path, duplicate collapse automatically
        found: dict[tuple[str, ...], Path] = {}
        for _ in range(max_paths):
            hub_names = self._dijkstra(penalties)
            if hub_names is None:  # unreachable end
                break
            key = tuple(hub_names)
            if key not in found:
                found[key] = self._build_path(key)
            # penalize internal hubs by +1 (but not start and end)
            for name in hub_names[1:-1]:
                penalties[name] = penalties.get(name, 0.0) + 1.0
        # sort the discovered path by real cost
        return sorted(found.values(), key=lambda p: self._path_cost(p))

    def _hub_entry_cost(self, hub: Hub, penalties: dict[str, float]) -> _Cost:
        """Return the cost of entering the given hub."""

        if not hub.zone_type.is_walkable:
            return _INF
        turns = hub.zone_type.movement_cost + penalties.get(hub.name, 0)
        priority_bonus = -1 if hub.zone_type is ZoneType.PRIORITY else 0
        return (turns, priority_bonus)

    def _build_path(self, hub_names: tuple[str, ...]) -> Path:
        """Takes a tuple of hub name and build a path with its cost"""

        step_costs = (0,) + tuple(
            self.graph.hubs[h].zone_type.movement_cost for h in hub_names[1:]
        )
        return Path(
            hubs=hub_names,
            step_costs=step_costs,
        )

    def _dijkstra(self, penalties: dict[str, float]) -> list[str] | None:
        """Run a single cost-weighted Dijkstra search.
        Args:
            penalties: Extra cost added to hub entry, keyed by hub name.
        Returns:
            the best Path found, or None if end is unreachable.
        """

        dist: dict[str, _Cost] = {self._start: (0, 0)}
        prev: dict[str, str] = {}
        heap: list[tuple[_Cost, str]] = [((0, 0), self._start)]
        while heap:
            cost, current = heapq.heappop(heap)
            if cost > dist.get(current, _INF):
                continue
            if current == self._end:
                break
            for nei in self.graph.neighbors(current):
                step = self._hub_entry_cost(self.graph.hubs[nei], penalties)
                if step == _INF:
                    continue
                new_cost = (cost[0] + step[0], cost[1] + step[1])
                if new_cost < dist.get(nei, _INF):
                    dist[nei] = new_cost
                    prev[nei] = current
                    heapq.heappush(heap, (new_cost, nei))
        if self._end not in dist:
            return None
        route = [self._end]
        while route[-1] != self._start:
            route.append(prev[route[-1]])
        route.reverse()
        return route

    def _path_cost(self, path: Path) -> int:
        """Turn cost of a past, ignoring priority tie-break."""

        return sum(
            self.graph.hubs[h].zone_type.movement_cost for h in path.hubs
        )
