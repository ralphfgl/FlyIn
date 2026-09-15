"""Drone representation."""

from dataclasses import dataclass, field
from enum import Enum, auto


class DroneState(Enum):
    """Current lifecycle state of a drone."""

    IDLE = auto()
    IN_TRANSIT = auto()
    DELIVERED = auto()


@dataclass
class Drone:
    """A single autonomous drone.
    Attributes:
        drone_id: unique identifier (e.g. "D1")
        current_hub: name of the hub it's in or departing from.
        transit_target: destination hub during a restricted move.
        transit_remaining: Turns left before arrival (0 when idle)
    """

    drone_id: str
    current_hub: str
    state: DroneState = DroneState.IDLE
    transit_target: str | None = None
    transit_remaining: int = 0
