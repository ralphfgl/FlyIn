"""Graph container for the drone network."""

from typing import Any, Self, Annotated

from pydantic import (
    BaseModel,
    model_validator,
    BeforeValidator,
    Field,
    PrivateAttr,
)

from .connections import Connection, canonical
from FlyIn.models.hub import Hub


def _index_hubs(value: Any) -> Any:
    """Takes a list of hub and index by name (no duplicate)"""

    if not isinstance(value, list) or not all(
        isinstance(h, Hub) for h in value
    ):
        return value
    hubs: dict[str, Hub] = {}
    for hub in value:
        if hub.name in hubs:
            raise ValueError(f"Duplicate hub name : {hub.name!r}")
        hubs[hub.name] = hub
    return hubs


def _index_connection(value: Any) -> Any:
    """Takes a list of conn, index it by its endpoints"""

    if not isinstance(value, list) or not all(
        isinstance(c, Connection) for c in value
    ):
        return value
    conns: dict[tuple[str, str], Connection] = {}
    for conn in value:
        if conn.endpoints in conns:
            a, b = conn.endpoints
            raise ValueError(f"Duplicate conn: {a!r}-{b!r}")
        conns[conn.endpoints] = conn
    return conns


class Graph:
    """Holds hubs, connections, and provides adjacency lookups."""

    hubs: Annotated[dict[str, Hub], BeforeValidator(_index_hubs)]
    connections: Annotated[
        dict[tuple[str, str], Connection],
        BeforeValidator(_index_connection),
    ] = Field(default_factory=dict)
    _adjacency: dict[str, list[str]] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _check_integrity(self) -> Self:
        """Check graph consistent, build adjacency lists"""

        adjacency: dict[str, list[str]] = {name: [] for name in self.hubs}
        for conn in self.connections.values():
            for name in conn.endpoints:
                if name not in self.hubs:
                    raise ValueError(
                        f"Connection references unknown hub: {name!r}"
                    )
            adjacency[conn.zone_a].append(conn.zone_b)
            adjacency[conn.zone_b].append(conn.zone_a)
        if sum(h.is_start for h in self.hubs.values()) != 1:
            raise ValueError(f"Expected only one start and end")
        if sum(h.is_end for h in self.hubs.values()) != 1:
            raise ValueError(f"Expected only one start and end")
        self._adjacency = adjacency
        return self

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
