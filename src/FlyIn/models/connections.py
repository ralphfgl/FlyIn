"""Connection between to hub (bidirectional)."""

from dataclasses import dataclass


def canonical(a: str, b: str) -> tuple[str, str]:
    """Return the sorted (a, b) pair, matching Connection's ordering"""
    return (a, b) if a <= b else (b, a)


@dataclass(frozen=True)
class Connection:
    """An edge between two hub.
    Canonical ordering is enforced at construction.
    Attributes:
        zone_a: first zone name (alpha smaller for canonical form)
        zone_b: second zone name
        max_link_capacity: maximum simultaneous drones in transit.
    """

    zone_a: str
    zone_b: str
    max_link_capacity: int = 1

    def __post_init__(self) -> None:
        if self.zone_a > self.zone_b:
            a, b = self.zone_b, self.zone_a
            object.__setattr__(self, "zone_a", a)
            object.__setattr__(self, "zone_b", b)

    def connects(self, name: str) -> bool:
        """Return True if this connection touches the given zone."""
        return name == self.zone_a or name == self.zone_b

    def other_end(self, name: str) -> str:
        """Return the zone at the opposite end of the connection."""

        if name == self.zone_a:
            return self.zone_b
        if name == self.zone_b:
            return self.zone_a
        raise ValueError(f"{name!r} is not part of connection {self!r}")

    @property
    def endpoints(self) -> tuple[str, str]:
        """Canonical endpoint pair, usabe as a dict key."""

        return (self.zone_a, self.zone_b)
