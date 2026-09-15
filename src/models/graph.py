"""Graph container for the drone network."""

from collections import defaultdict

from .connections import Connection, canonical
from .hub import Hub


class Graph:
    """Holds hubs, connections, and provides adjacency lookups."""

    def __init__(self) -> None:
        """Initialize an empty graph."""

        self.hubs: dict[str, Hub] = {}
        self.connections: dict[tuple[str, str], Connection] = {}
        self._adjacency: dict[str, list[str]] = defaultdict(list)

    def add_hub(self, hub: Hub) -> None:
        """Register a hub. Raises ValueError on duplicate names."""

        if hub.name in self.hubs:
            raise ValueError(f"Duplicate hub name: {hub.name!r}")
        self.hubs[hub.name] = hub
        # ensure all hub have an adjacency entry even if it has not edges
        _ = self._adjacency[hub.name]

    def add_connection(self, conn: Connection) -> None:
        """Register a connection. Raises on duplicates or unknown hubs."""

        key = conn.endpoints
        if key in self.connections:
            raise ValueError(f"Duplicate connection: {key[0]!r}-{key[1]!r}")
        for name in key:
            if name not in self.hubs:
                raise ValueError(
                    f"Connection references unknwon hub: {name!r}"
                )
            self.connections[key] = conn
            self._adjacency[conn.zone_a].append(conn.zone_b)
            self._adjacency[conn.zone_b].append(conn.zone_a)

    def neighbors(self, hub_name: str) -> list[str]:
        """Return all hub names adajcent to the given hub."""

        return list(self._adjacency.get(hub_name, []))

    def get_connection(self, a: str, b: str) -> Connection:
        """Retrieve the connection between two hubs."""

        return self.connections[canonical(a, b)]

    @property
    def start(self) -> Hub:
        """Return the start"""

        for hub in self.hubs.values():
            if hub.is_start:
                return hub
        raise ValueError("Graph has no start hub.")

    @property
    def end(self) -> Hub:
        """Return the end"""

        for hub in self.hubs.values():
            if hub.is_end:
                return hub
        raise ValueError("Graph has no end hub.")
