"""Parser for maps."""

import re
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, PositiveInt, ValidationError

from FlyIn.models.connections import Connection, ConnectionMeta
from FlyIn.models.graph import Graph
from FlyIn.models.hub import Hub, HubMeta


class ParseError(Exception):
    """Raised when the input map is malformed (0 means more than 0 line)."""

    def __init__(self, line_no: int, message: str) -> None:
        super().__init__(f"Line {line_no}: {message}" if line_no else message)
        self.line_no = line_no
        self.message = message


class ParsedMap(BaseModel):
    """The result of parsing a map file."""

    model_config = ConfigDict(frozen=True)

    graph: Graph
    nb_drones: PositiveInt


class _Header(BaseModel):
    """The ``nb_drones:`` line."""

    nb_drones: PositiveInt


_TOKEN = r"[^\s\[\]#]+"
_NB_DRONES_RE = re.compile(r"nb_drones:\s*(?P<value>\S+)$")
_HUB_RE = re.compile(
    r"(?P<kind>start_hub|end_hub|hub):\s+"
    rf"(?P<name>{_TOKEN})\s+(?P<x>{_TOKEN})\s+(?P<y>{_TOKEN})\s*"
    r"(?P<meta>\[.*\])?$"
)
_CONN_RE = re.compile(
    r"connection:\s*"
    r"(?P<a>[^\s\[\]#-]+)-(?P<b>[^\s\[\]#-]+)\s*"
    r"(?P<meta>\[.*\])?$"
)

_M = TypeVar("_M", bound=BaseModel)


def _format_errors(exc: ValidationError) -> str:
    """Turn a pydantic ValidationError into a short one-line message."""
    parts = []
    for err in exc.errors(include_url=False):
        where = ".".join(str(p) for p in err["loc"])
        msg = err["msg"].removeprefix("Value error, ")
        parts.append(f"{where}: {msg}" if where else msg)
    return "; ".join(parts)


def _validate(model: type[_M], data: dict[str, Any], line_no: int) -> _M:
    """Validate ``data`` with a pydantic model, or raise a ParseError."""
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ParseError(line_no, _format_errors(exc)) from exc


# Metadata


def _parse_metadata(raw: str | None, line_no: int) -> dict[str, str]:
    """Split an optional ``[k=v k=v ...]`` block into a dict of strings.

    Only the shape is checked here (and duplicate keys, which a dict would
    silently swallow). Keys and values are validated by the pydantic models.
    """
    meta: dict[str, str] = {}
    for token in (raw or "")[1:-1].split():
        key, sep, value = token.partition("=")
        if not (key and sep and value):
            raise ParseError(line_no, f"Invalid metadata entry: {token!r}")
        if key in meta:
            raise ParseError(line_no, f"Duplicate metadata key: {key!r}")
        meta[key] = value
    return meta


# Line parsers


def _parse_nb_drones(line: str, line_no: int) -> int:
    m = _NB_DRONES_RE.match(line)
    if not m:
        raise ParseError(line_no, f"Malformed nb_drones line: {line!r}")
    return _validate(_Header, {"nb_drones": m["value"]}, line_no).nb_drones


def _parse_hub_line(line: str, line_no: int) -> Hub:
    m = _HUB_RE.match(line)
    if not m:
        raise ParseError(line_no, f"Malformed hub line: {line!r}")
    meta = _validate(HubMeta, _parse_metadata(m["meta"], line_no), line_no)
    return _validate(
        Hub,
        {
            "name": m["name"],
            "x": m["x"],
            "y": m["y"],
            "is_start": m["kind"] == "start_hub",
            "is_end": m["kind"] == "end_hub",
            **meta.model_dump(),
        },
        line_no,
    )


def _parse_connection_line(line: str, line_no: int) -> Connection:
    m = _CONN_RE.match(line)
    if not m:
        raise ParseError(line_no, f"Malformed connection line: {line!r}")
    meta = _validate(
        ConnectionMeta, _parse_metadata(m["meta"], line_no), line_no
    )
    return _validate(
        Connection,
        {"zone_a": m["a"], "zone_b": m["b"], **meta.model_dump()},
        line_no,
    )


# File parser


def parse_file(path: str | Path) -> ParsedMap:
    """Parse a map file into a Graph and the number of drones."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ParseError(0, f"Cannot read {str(path)!r}: {exc}") from exc

    nb_drones: int | None = None
    hubs: list[Hub] = []
    conns: list[Connection] = []

    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        if line.startswith("nb_drones:"):
            if nb_drones is not None:
                raise ParseError(line_no, "Duplicate nb_drones declaration")
            nb_drones = _parse_nb_drones(line, line_no)
        elif line.startswith(("start_hub:", "end_hub:", "hub:")):
            hubs.append(_parse_hub_line(line, line_no))
        elif line.startswith("connection:"):
            conns.append(_parse_connection_line(line, line_no))
        else:
            raise ParseError(line_no, f"Unrecognized line: {line!r}")

    if nb_drones is None:
        raise ParseError(0, "Missing nb_drones declaration")
    if not hubs:
        raise ParseError(0, "Map contains no hubs")
    graph = _validate(Graph, {"hubs": hubs, "connections": conns}, 0)
    return ParsedMap(graph=graph, nb_drones=nb_drones)
