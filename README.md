*This activity has been created as part of the 42 curriculum by rfeghali.*

# Fly-In

## Description

Fly-In is a drone routing simulator. Given a map describing hubs, connections, zone types, and capacities, it finds multiple paths from a start hub to an end hub and simulates a fleet of drones moving along them turn by turn, respecting every constraint.

The goal is to deliver all drones to the end hub in the fewest possible turns while never violating capacity limits on hubs or connections.

## Instructions

### Installation and execution

```bash
uv sync                              # Install dependencies
make run MAP=maps/easy/01_linear_path.txt
make visualize MAP=maps/hard/03_ultimate_challenge.txt
make lint                            # Run flake8 and mypy
```

### Running without `make`

```bash
uv run python -m FlyIn maps/easy/01_linear_path.txt --max-paths 6 [--visualize]
```

## Algorithm Choices and Implementation Strategy

### 1. Parsing (`parser.py`)

A regex parser with Pydantic validation.

Each `nb_drones`, `hub:`, `start_hub:`, `end_hub:`, and `connection:` line is validated individually. Duplicates, self-loops, and unknown hubs are rejected during graph construction.

### 2. Path Discovery (`pathfinder.py`)

A Yen-style **penalty-iterated Dijkstra** algorithm:

- Runs a cost-weighted Dijkstra search up to `max_paths` times.
- Adds a `+1` penalty to internal hubs already used, encouraging subsequent searches to find different routes.
- Gives priority zones a `-1` tie-breaker.
- Excludes blocked zones.
- Assigns a cost of `2` turns to restricted zones.


### 3. Scheduling (`scheduler.py`)

Paths are assigned to drones using **round-robin assignment** at startup and then cached. Paths are never recomputed during the simulation.

Each turn follows three steps:

1. **Advance drones in transit:** Move drones through restricted zones.
2. **Move idle drones:** Check hub capacity and link capacity before committing to a move.
3. **Release links:** Free the links used during the current turn.

Congestion is handled by **waiting**. If a move is blocked, the drone retries it on the next turn.

### 4. Complexity

- **Path discovery:** `O(K · (H + C) · log H)`
- **Each simulation turn:** `O(D)`

Where:

- `K` = maximum number of paths
- `H` = number of hubs
- `C` = number of connections
- `D` = number of drones

## Visual Representation

Fly-In provides two complementary visualizers.

### TextVisualizer

- Displays one block per turn, listing drone IDs at each hub and the number of drones in transit.
- Colors hub names using the parsed `color=` attribute with ANSI colors.

### PygameVisualizer

- Draws the graph using the parsed hub colors.
- Displays live drone counts and drone-ID lists beneath each hub.
- Shows per-link occupancy (at previous turn) over max-capacity


## Example

### Input

File: `maps/easy/01_linear_path.txt`

```text
nb_drones: 2
start_hub: start 0 0 [color=green]
hub: waypoint1 1 0 [color=blue]
hub: waypoint2 2 0 [color=blue]
end_hub: goal 3 0 [color=red]
connection: start-waypoint1
connection: waypoint1-waypoint2
connection: waypoint2-goal
```

### Expected Output

```text
D1-waypoint1
D2-waypoint1 D1-waypoint2
D2-waypoint2 D1-goal
D2-goal
```


## Resources

- [Dijkstra's Algorithm](https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm)
- [How Dijkstra's Algorithm Works (YouTube)](https://www.youtube.com/watch?v=EFg3u_E6eHU)
- [Yen's K-Shortest Paths Algorithm](https://en.wikipedia.org/wiki/Yen%27s_algorithm)
- [Pydantic v2 Documentation](https://docs.pydantic.dev/latest/)
- [Pygame Documentation](https://www.pygame.org/docs/)
- [uv Documentation](https://docs.astral.sh/uv/)

## AI Usage

AI assistance was used for:

- Reviewing and cleaning up the code, including naming consistency and mypy errors.
- Correcting this README.
- Explaining algorithmic complexity.
