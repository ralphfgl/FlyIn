"""Hub representation."""

from dataclasses import dataclass, field

from .zone_type import ZoneType
from models import zone_type


@dataclass
class Hub:
    """A zone in the drone network.
    Attributes:
        name: unique identifier for the hub
        x, y : coordinate (int)
        zone_type: (normal, restricted...)
        color: optional display color.
        max_drones: max simultaneous occupancy.
        is_start, is_end: whether this is the start or end hub.
    """

    name: str
    x: int
    y: int
    zone_type: ZoneType = ZoneType.NORMAL
    color: str | None = None
    max_drones: int = 1
    is_start: bool = False
    is_end: bool = False
    # mutable runtime state
    current_drones: list[str] = field(default_factory=list, compare=False)

    @property
    def effective_capacity(self) -> int:
        """Return the capacity actually enforced (start/end are unlimited)."""
        if self.is_start or self.is_end:
            # NOTE: can use float("inf") instead..
            return 10**9
        return self.max_drones

    def has_space_for(self, drone_id: str, outgoing: int = 0) -> bool:
        """Check if a drone can enter this hub this turn.
        Args:
            drone_id: the drone attempting to enter.
            outgoing: nb of drones that will leave this turn.
        """

        projected = len(self.current_drones) - outgoing
        return projected < self.effective_capacity
