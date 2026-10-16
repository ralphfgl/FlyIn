"""Hub representation."""

from typing import Self

from FlyIn.models.zone_type import ZoneType

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)


class HubMeta(BaseModel):
    """Optional data for a hub line

    Attributes:
        zone_type: (normal, restricted...)
        color: optional display color.
        max_drones: max simultaneous occupancy.

    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    zone_type: ZoneType = Field(default=ZoneType.NORMAL, alias="zone")
    color: str | None = None
    max_drones: PositiveInt = 1


class Hub(HubMeta):
    """A zone in the drone network.

    Attributes:
        name: unique identifier for the hub
        x, y : coordinate (int)
        is_start, is_end: whether this is the start or end hub.
        current_drones: mutable runtime state (ids of drone in the hub)
    """

    name: str
    x: int
    y: int
    is_start: bool = False
    is_end: bool = False
    current_drones: list[str] = Field(
        default_factory=list, exclude=True, repr=False
    )

    @field_validator("name")
    @classmethod
    def _name_has_dash(cls, value: str) -> str:
        if "-" in value:
            raise ValueError(f"Hub name cannot contain '-' : {value!r}")
        return value

    @model_validator(mode="after")
    def _not_start_and_end(self) -> Self:
        if self.is_start and self.is_end:
            raise ValueError("A hub cannot be both start and end.")
        return self

    @property
    def effective_capacity(self) -> int | float:
        """Return the capacity actually enforced (start/end are unlimited)."""

        if self.is_start or self.is_end:
            return float("inf")
        return int(self.max_drones)

    def has_space_for(self, drone_id: str, outgoing: int = 0) -> bool:
        """Check if a drone can enter this hub this turn.
        Args:
            drone_id: the drone attempting to enter.
            outgoing: nb of drones that will leave this turn.
        """

        projected = len(self.current_drones) - outgoing
        return projected < self.effective_capacity
