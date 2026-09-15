"""Zone type definitions for the drone routing network."""

from enum import Enum


class ZoneType(Enum):
    """Enumeration of possible zone types with movement costs."""

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"

    @property
    def movement_cost(self) -> int:
        """Return the number of turns required to enter this zone type."""
        if self is ZoneType.RESTRICTED:
            return 2
        if self is ZoneType.BLOCKED:
            return -1
        return 1

    @property
    def is_walkable(self) -> bool:
        """Return True if drones can enter this zone type."""
        return self is not ZoneType.BLOCKED
