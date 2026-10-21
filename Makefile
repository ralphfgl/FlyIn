PYTHON = uv run python

MAP ?= maps/easy/01_linear_path.txt
MAX_PATHS ?= 2

help:
	@echo "Available commands:"
	@echo "  make run              Run the simulation"
	@echo "  make visualize       Run with visualization"
	@echo "  make lint             Check code with mypy and flake8"

install:
	uv sync

run:
	$(PYTHON) -m FlyIn $(MAP) --max-paths $(MAX_PATHS)

visualize:
	$(PYTHON) -m FlyIn $(MAP) --max-paths $(MAX_PATHS) --visualize

debug:
	$(PYTHON) -m pdb src/FlyIn/__main__.py $(MAP)


lint:
	flake8 src/
	mypy src/ --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

clean:
	@ find . -type d -name ".mypy_cache" -exec rm -rf {} +
	@ find . -type d -name "__pycache__" -exec rm -rf {} +

.PHONY: help run visualize lint format check test
