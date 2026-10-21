"""Turn by turn simulation engine."""

from pydantic import BaseModel

from FlyIn.visualizer import TextVisualizer
from FlyIn.pygame_visualizer import PygameVisualizer
from FlyIn.models.graph import Graph
from FlyIn.models.hub import Hub
from FlyIn.pathfinder import Path


class DroneState(BaseModel):
    """Dynamic runtime state for one drone."""

    drone_id: str
    path: tuple[str, ...]
    path_index: int = 0  # index of the current hub
    delivered: bool = False
    transit_target: str | None = None
    transit_turns_left: int = 0

    @property
    def current_hub(self) -> str:
        return self.path[self.path_index]

    @property
    def next_hub(self) -> str | None:
        """Next hub on the path, None if at the end."""

        if self.path_index + 1 >= len(self.path):
            return None
        return self.path[self.path_index + 1]


class Scheduler:
    """Runs the simulation."""

    def __init__(
        self,
        graph: Graph,
        paths: list[Path],
        nb_drones: int,
        visualizer: TextVisualizer | PygameVisualizer | None = None,
    ) -> None:
        if not paths:
            raise ValueError("Scheduler requires at least one path")
        self.graph = graph
        self.paths = paths
        self.nb_drones = nb_drones
        self.drones: list[DroneState] = []
        for i in range(nb_drones):
            path = paths[i % len(paths)]
            self.drones.append(
                DroneState(drone_id=f"D{i + 1}", path=path.hubs)
            )
        # runtime occupancy
        self._occupancy: dict[str, set[str]] = {h: set() for h in graph.hubs}
        for d in self.drones:
            self._occupancy[graph.start.name].add(d.drone_id)
        # restricted hub name -> ids of d currently traveling to it
        self._inbound: dict[str, set[str]] = {h: set() for h in graph.hubs}
        self._by_id: dict[str, DroneState] = {
            d.drone_id: d for d in self.drones
        }
        # runtime conn: (a,b) -> drone count on the link
        self._in_transit: dict[tuple[str, str], int] = {}
        # checklist to reduce link occupancy at end of turn
        self._release_at_end: list[tuple[str, str]] = []
        self.turns: list[str] = []
        self._visualizer = visualizer

    def run(self, max_turns: int = 10_000) -> list[str]:
        """Run the sim.

        Args:
            max_turns: max nb of turn in a sim
        Returns:
            A list of turn strings, listing turn movement.
        """

        for _ in range(max_turns):
            if all(d.delivered for d in self.drones):
                return self.turns
            line = self._step()
            if line:
                self.turns.append(line)
        raise RuntimeError("Simulation exceeded max_turns.")

    def _step(self) -> str:
        """Advance one turn. Returns the movement line."""

        moves: list[str] = []
        landing: list[DroneState] = []
        # 1. deliver drone in transit
        for d in self.drones:
            if d.transit_target is not None:
                d.transit_turns_left -= 1
                if d.transit_turns_left == 0:
                    key = self.graph.get_connection(
                        d.current_hub, d.transit_target
                    ).endpoints
                    # decrease nb of d in transit in conn
                    self._in_transit[key] = max(
                        0, self._in_transit.get(key, 1) - 1
                    )
                    landing.append(d)
        # 2. try to move idle d
        for d in self.drones:
            if d.delivered or d.transit_target is not None:
                continue
            self._try_move(d, moves)
        # 3. land arrivals after leavers have vacated their hubs
        for d in landing:
            self._finish_transit(d, moves)
        # 4. free the links used during this turn
        for key in self._release_at_end:
            self._in_transit[key] = max(0, self._in_transit.get(key, 1) - 1)
        self._release_at_end.clear()
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
        """Turn execution"""

        target = d.next_hub
        if target is None:
            return
        target_hub = self.graph.hubs[target]
        if not target_hub.zone_type.is_walkable:
            return
        cost = target_hub.zone_type.movement_cost
        conn = self.graph.get_connection(d.current_hub, target)
        key = conn.endpoints
        used = self._in_transit.get(key, 0)
        if used >= conn.max_link_capacity:
            return
        if cost == 2:
            if not self._can_depart_restricted(target_hub):
                return
            self._in_transit[key] = used + 1
            self._inbound[target].add(d.drone_id)
            self._occupancy[d.current_hub].discard(d.drone_id)
            d.transit_target = target
            d.transit_turns_left = cost - 1
            moves.append(f"{d.drone_id}-{conn.zone_a}-{conn.zone_b}")
            return
        if not self._can_enter(target_hub, d.drone_id):
            return
        self._in_transit[key] = used + 1
        self._release_at_end.append(key)
        self._move_now(d, target, moves)

    def _can_depart_restricted(self, hub: Hub) -> bool:
        """Allow drones to travel through restricted link,
        even if the destination hub is at full capacity.
        """

        end = self.graph.end
        if hub.name == end.name:
            return True
        total = 0
        # drone that want to leave the restricted hub to end
        wanting = 0
        conn = None
        # count d in restrict hub and in its link
        for name in self._occupancy[hub.name] | self._inbound[hub.name]:
            d = self._by_id[name]
            # add one if drone traveling toward the hub we are cheking
            idx = d.path_index + (1 if d.transit_target == hub.name else 0)
            nxt = d.path[idx + 1] if idx + 1 < len(d.path) else None
            total += 1
            if nxt == end.name and end.zone_type.movement_cost == 1:
                conn = self.graph.get_connection(hub.name, nxt)
                wanting += 1
        leaving = min(wanting, conn.max_link_capacity) if conn else 0
        return total - leaving < hub.effective_capacity

    def _can_enter(self, hub: Hub, drone_id: str) -> bool:
        """Check capacity of destination hub"""

        return (
            len(self._occupancy[hub.name]) + len(self._inbound[hub.name])
            < hub.effective_capacity
        )

    def _move_now(self, d: DroneState, target: str, moves: list[str]) -> None:
        """Single-turn move for a drone."""

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
        assert (
            target == self.graph.end.name
            or len(self._occupancy[target])
            < self.graph.hubs[target].effective_capacity
        ), f"{target} overfull on landing"
        self._inbound[target].discard(d.drone_id)
        self._occupancy[target].add(d.drone_id)
        d.path_index += 1
        d.transit_target = None
        d.transit_turns_left = 0
        if target == self.graph.end.name:
            d.delivered = True
        moves.append(f"{d.drone_id}-{target}")
