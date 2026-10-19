"""Named color palette"""

from __future__ import annotations

PALETTE: dict[str, tuple[int, int, int]] = {
    "red": (220, 50, 50),
    "green": (70, 180, 100),
    "yellow": (235, 200, 40),
    "blue": (80, 145, 220),
    "orange": (240, 150, 50),
    "purple": (150, 80, 200),
    "brown": (140, 90, 50),
    "maroon": (110, 30, 60),
    "darkred": (140, 20, 20),
    "gold": (220, 180, 40),
    "violet": (170, 80, 220),
    "crimson": (200, 20, 70),
    "cyan": (60, 200, 200),
    "lime": (150, 230, 60),
    "magenta": (220, 80, 200),
    "black": (40, 40, 40),
    "white": (240, 240, 240),
    "gray": (140, 140, 140),
    "grey": (140, 140, 140),
}

_FALLBACK = (140, 140, 140)


def rgb(name: str | None) -> tuple[int, int, int]:
    """Return RGB color value, or grey if unknown"""

    if not name:
        return _FALLBACK
    return PALETTE.get(name.lower(), _FALLBACK)


def ansi_fg(name: str | None) -> str:
    """Return an ANSI escape code for a color name."""

    r, g, b = rgb(name)
    return f"\033[38;2;{r};{g};{b}m"


ANSI_RESET = "\033[0m"
