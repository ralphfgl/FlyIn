"""Turn by turn simulation engine."""

from dataclasses import dataclass, field

from .vizualizer import TextVisualizer
from .models.graph import Graph
from .models.hub import Hub
from .pathfinder import Path


@dataclass
class DroneState:
    """Runtime state for one drone."""

    drone_id: str
    path: tuple[str, ...]  # sequence of hub name
    path_index: int = 0  # index of the hub the drone is currently at
    delivered: bool = False
    transit_target: str | None = None
    transit_turns_left: int = 0

    @property
    def current_hub(self) -> str:
        """Name of the hub the drone is currently occupying."""

        return self.path[self.path_index]

    @property
    def next_hub(self) -> str | None:
        """The next hub on the path, or None if at the end."""

        if self.path_index + 1 >= len(self.path):
            return None
        return self.path[self.path_index + 1]


class Scheduler:
    """Runs the simulation and records the output lines."""

    def __init__(
        self,
        graph: Graph,
        paths: list[Path],
        nb_drones: int,
        visualizer: TextVisualizer | None = None,
    ) -> None:
        if not paths:
            raise ValueError("Scheduler requires at least one path")
        self.graph = graph
        self.paths = paths
        self.nb_drones = nb_drones
        self.drones: list[DroneState] = []
        # assign drones to path round-robin
        for i in range(nb_drones):
            path = paths[i % len(paths)]
            self.drones.append(
                DroneState(drone_id=f"D{i + 1}", path=path.hubs)
            )
        # runtime occupancy: maps hub name -> set of drone ids currently here
        self._occupancy: dict[str, set[str]] = {h: set() for h in graph.hubs}
        start_name = graph.start.name
        for d in self.drones:
            self._occupancy[start_name].add(d.drone_id)
        # runtime connection usage: map (a, b) -> count of drones in transit
        self._in_transit: dict[tuple[str, str], int] = {}
        self.turns: list[str] = []
        self._visualizer = visualizer

    # public API
    def run(self, max_turns: int = 10_000) -> list[str]:
        """Run the sim.
        Args:
            max_turns: safety cap to prevent infinite sim.
        Returns:
            A list of turn strings, each listing that turns movements.
        """

        for _ in range(max_turns):
            if all(d.delivered for d in self.drones):
                return self.turns
            line = self._step()
            if line:
                self.turns.append(line)
        raise RuntimeError("Simulation exceeded max_turns without finishing.")

    # internals
    def _step(self) -> str:
        """Advance one turn. Returns the formatted movement line."""

        moves: list[str] = []
        # Phase 1: advance in-transit drones (restricted-zone arrivals).
        for d in self.drones:
            if d.transit_target is not None:
                d.transit_turns_left -= 1
                if d.transit_turns_left == 0:
                    self._finish_transit(d, moves)
        # Phase 2: try to move idle drones
        for d in self.drones:
            if d.delivered or d.transit_target is not None:
                continue
            self._try_move(d, moves)
        line = " ".join(moves)
        if self._visualizer is not None:
            self._visualizer.render(
                turn=len(self.turns) + 1,
                movement_line=line,
                occupancy=self._occupancy,
                in_transit=self._in_transit,
            )
        return line

    def _try_move(self, d: DroneState, moves: list[str]) -> None:
        """Attempt a single-step move for the given drone."""

        target = d.next_hub
        if target is None:
            return  # already at end, should not happen
        target_hub = self.graph.hubs[target]
        if not target_hub.zone_type.is_walkable:
            return  # blocked, should not happen if pathfinder correct
        cost = target_hub.zone_type.movement_cost
        if cost == 2:
            # restricted: begin a 2-turn transit thru connection
            conn = self.graph.get_connection(d.current_hub, target)
            key = conn.endpoints()
            used = self._in_transit.get(key, 0)
            if used >= conn.max_link_capacity:
                return  # connection busy
            # NOTE: we dont wait for destination space, the drone commit to the connection
            self._in_transit[key] = used + 1
            # discard -> set method to remove a key
            self._occupancy[d.current_hub].discard()
            d.transit_target = target
            d.transit_turns_left = 2
            moves.append(f"{d.drone_id}-{conn.zone_a}-{conn.zone_b}")
            return
        if not self._can_enter(target_hub, d.drone_id):
            return
        self._move_now(d, target, moves)

    def _can_enter(self, hub: Hub, drone_id: str):
        """Check whether hub has capaciy for one more drone this turn."""

        # Drones currently in the hub that will LEAVE this turn are already removed from occupancy in _move_now/ _try_move, so occupancy reflects the 'already moved out' state
        return len(self._occupancy[hub.name]) < hub.effective_capacity

    def _move_now(self, d: DroneState, target: str, moves: list[str]) -> None:
        """Commit a single-turn move for a drone."""

        self._occupancy[d.current_hub].discard(d.drone_id)
        self._occupancy[target].add(d.drone_id)
        d.path_index += 1
        if target == self.graph.end.name:
            d.delivered = True
        moves.append(f"{d.drone_id}-{target}")

    def _finish_transit(self, d: DroneState, moves: list[str]) -> None:
        """Complete a restricted-zone arrival."""

        target = d.transit_target
        assert target is not None
        conn = self.graph.get_connection(d.current_hub, target)
        key = conn.endpoints
        # guard against negative value
        self._in_transit[key] = max(0, self._in_transit.get(key, 1) - 1)
        # the drone must arrive, no capacity check on destination
        self._occupancy[target].add(d.drone_id)
        d.path_index += 1
        d.transit_target = None
        d.transit_turns_left = 0
        if target == self.graph.end.name:
            d.delivered = True
        moves.append(f"{d.drone_id}-{target}")
