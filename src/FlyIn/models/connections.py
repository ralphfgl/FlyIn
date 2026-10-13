"""Connection between to hub (bidirectional)."""

from typing import Self

from pydantic import BaseModel, model_validator, PositiveInt, ConfigDict


def canonical(a: str, b: str) -> tuple[str, str]:
    """Return the sorted (a, b) pair, matching Connection's ordering"""
    return (a, b) if a <= b else (b, a)


class ConnectionMeta(BaseModel):
    """Optional metadata for a connection.

    Attribute:
        max_link_capacity: maximum simultaneous drones in transit.
    """

    model_config = ConfigDict(extra="forbid")
    max_link_capacity: PositiveInt = 1


class Connection(ConnectionMeta):
    """An edge between two hub.
    Canonical ordering is enforced at construction.

    Attributes:
        zone_a: first zone name (alpha smaller for canonical form)
        zone_b: second zone name
    """

    zone_a: str
    zone_b: str

    @model_validator(mode="after")
    def _validate_and_order(self) -> Self:
        """Reject self loop and put the endpoints in canonical order."""

        if self.zone_a == self.zone_b:
            raise ValueError(f"Hub cant be linked to itself: {self.zone_a!r}")
        a, b = canonical(self.zone_a, self.zone_b)
        object.__setattr__(self, "zone_a", a)
        object.__setattr__(self, "zone_b", b)
        return self

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
        """Canonical endpoint pair, usabe as a dict key
        cause they are unique.
        """

        return (self.zone_a, self.zone_b)
