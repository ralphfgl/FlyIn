"""Input file parser for drone network maps."""

import re
from dataclasses import dataclass
from pathlib import Path

from .models.connections import Connection
from .models.graph import Graph
from .models.hub import Hub
from .models.zone_type import ZoneType


class ParseError(Exception):
    """Raised when the input map is malformed."""

    def __init__(self, line_no: int, message: str) -> None:
        super().__init__(f"Line {line_no}: {message}")
        self.line_no = line_no
        self.message = message


# Result type


@dataclass(frozen=True)
class ParsedMap:
    """The result of parsing a map file."""

    graph: Graph
    nb_drones: int


# Regexes — one per line kind, each anchored and named

_METADATA_RE = re.compile(r"\[([^\]]*)\]\s*$")
_NB_DRONES_RE = re.compile(r"nb_drones:\s*(\d+)\s*$")
_HUB_RE = re.compile(
    r"(?P<kind>start_hub|end_hub|hub):\s+"
    r"(?P<name>\S+)\s+"
    r"(?P<x>-?\d+)\s+"
    r"(?P<y>-?\d+)\s*"
    r"(?P<meta>\[.*\])?$"
)
_CONN_RE = re.compile(
    r"connection:\s*"
    r"(?P<a>\S+?)-(?P<b>\S+?)\s*"
    r"(?P<meta>\[.*\])?$"
)

_META_ENTRY_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>\S+)")


# Metadata


def _parse_metadata(raw: str | None, line_no: int) -> dict[str, str]:
    """Parse an optional ``[k=v k=v ...]`` block into a dict."""
    if raw is None:
        return {}
    inner = raw[1:-1]  # strip [ and ]
    meta: dict[str, str] = {}
    pos = 0
    while pos < len(inner):
        # Skip whitespace.
        while pos < len(inner) and inner[pos].isspace():
            pos += 1
        if pos >= len(inner):
            break
        m = _META_ENTRY_RE.match(inner, pos)
        if not m:
            raise ParseError(
                line_no, f"Invalid metadata entry at {inner[pos:]!r}"
            )
        key, value = m.group("key"), m.group("value")
        if key in meta:
            raise ParseError(line_no, f"Duplicate metadata key: {key!r}")
        meta[key] = value
        pos = m.end()
    return meta


# Field parsers


def _positive_int(value: str, field: str, line_no: int) -> int:
    """Parse a positive integer or raise ParseError."""
    try:
        n = int(value)
    except ValueError as exc:
        raise ParseError(
            line_no, f"{field} must be an integer, got {value!r}"
        ) from exc
    if n <= 0:
        raise ParseError(line_no, f"{field} must be > 0, got {n}")
    return n


def _parse_zone_type(value: str, line_no: int) -> ZoneType:
    try:
        return ZoneType(value)
    except ValueError as exc:
        raise ParseError(line_no, f"Invalid zone type: {value!r}") from exc


# Intermediate line records (parsed, not yet validated against the graph)


@dataclass(frozen=True)
class _HubDecl:
    line_no: int
    kind: str
    name: str
    x: int
    y: int
    meta: dict[str, str]


@dataclass(frozen=True)
class _ConnDecl:
    line_no: int
    a: str
    b: str
    meta: dict[str, str]


# Line parsers


def _parse_hub_line(line: str, line_no: int) -> _HubDecl:
    m = _HUB_RE.match(line)
    if not m:
        raise ParseError(line_no, f"Malformed hub line: {line!r}")
    name = m.group("name")
    if "-" in name:
        raise ParseError(line_no, f"Hub name cannot contain '-': {name!r}")
    meta = _parse_metadata(m.group("meta"), line_no)
    return _HubDecl(
        line_no=line_no,
        kind=m.group("kind"),
        name=name,
        x=int(m.group("x")),
        y=int(m.group("y")),
        meta=meta,
    )


def _parse_connection_line(line: str, line_no: int) -> _ConnDecl:
    m = _CONN_RE.match(line)
    if not m:
        raise ParseError(line_no, f"Malformed connection line: {line!r}")
    a, b = m.group("a"), m.group("b")
    if a == b:
        raise ParseError(
            line_no, f"Connection cannot link a hub to itself: {a!r}"
        )
    meta = _parse_metadata(m.group("meta"), line_no)
    return _ConnDecl(line_no=line_no, a=a, b=b, meta=meta)


# Two-pass file parser


def parse_file(path: str | Path) -> ParsedMap:
    """Parse a map file into a Graph and the number of drones."""
    nb_drones: int | None = None
    hubs: list[_HubDecl] = []
    conns: list[_ConnDecl] = []

    with open(path, "r", encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh, start=1):
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue

            # nb_drones — must appear exactly once.
            if line.startswith("nb_drones:"):
                if nb_drones is not None:
                    raise ParseError(
                        line_no, "Duplicate nb_drones declaration"
                    )
                m = _NB_DRONES_RE.match(line)
                if not m:
                    raise ParseError(
                        line_no, f"Malformed nb_drones line: {line!r}"
                    )
                nb_drones = _positive_int(m.group(1), "nb_drones", line_no)
                continue

            if line.startswith(("start_hub:", "end_hub:", "hub:")):
                hubs.append(_parse_hub_line(line, line_no))
                continue

            if line.startswith("connection:"):
                conns.append(_parse_connection_line(line, line_no))
                continue

            raise ParseError(line_no, f"Unrecognized line: {line!r}")

    if nb_drones is None:
        raise ParseError(0, "Missing nb_drones declaration")
    if not hubs:
        raise ParseError(0, "Map contains no hubs")

    # ---- Pass 2: build the graph -----------------------------------------
    graph = Graph()

    for decl in hubs:
        graph.add_hub(_build_hub(decl))

    for decl in conns:
        graph.add_connection(_build_connection(decl))

    _validate_start_end(graph)
    return ParsedMap(graph=graph, nb_drones=nb_drones)


def _build_hub(decl: _HubDecl) -> Hub:
    """Turn a parsed hub declaration into a Hub, validating metadata."""
    meta = decl.meta
    zone_type = _parse_zone_type(meta.get("zone", "normal"), decl.line_no)
    max_drones = (
        _positive_int(meta["max_drones"], "max_drones", decl.line_no)
        if "max_drones" in meta
        else 1
    )
    unknown = set(meta) - {"zone", "max_drones", "color"}
    if unknown:
        raise ParseError(
            decl.line_no, f"Unknown hub metadata keys: {sorted(unknown)}"
        )
    return Hub(
        name=decl.name,
        x=decl.x,
        y=decl.y,
        zone_type=zone_type,
        color=meta.get("color"),
        max_drones=max_drones,
        is_start=(decl.kind == "start_hub"),
        is_end=(decl.kind == "end_hub"),
    )


def _build_connection(decl: _ConnDecl) -> Connection:
    """Turn a parsed connection declaration into a Connection."""
    meta = decl.meta
    capacity = (
        _positive_int(
            meta["max_link_capacity"], "max_link_capacity", decl.line_no
        )
        if "max_link_capacity" in meta
        else 1
    )
    unknown = set(meta) - {"max_link_capacity"}
    if unknown:
        raise ParseError(
            decl.line_no,
            f"Unknown connection metadata keys: {sorted(unknown)}",
        )
    # Connection canonicalizes internally; no need to pre-sort here.
    return Connection(decl.a, decl.b, capacity)


def _validate_start_end(graph: Graph) -> None:
    """Ensure exactly one start hub and one end hub."""
    starts = [h for h in graph.hubs.values() if h.is_start]
    ends = [h for h in graph.hubs.values() if h.is_end]
    if len(starts) != 1:
        raise ParseError(
            0, f"Expected exactly one start_hub, found {len(starts)}"
        )
    if len(ends) != 1:
        raise ParseError(0, f"Expected exactly one end_hub, found {len(ends)}")
