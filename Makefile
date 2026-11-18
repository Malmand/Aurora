# AURORA: common tasks. Everything below "figures" reads committed results only.
.PHONY: install test numbers figures check all

install:
	pip install -e ".[dev]"

test:
	pytest -q

numbers:          ## every deck number -> results/headline.json, docs/headline_numbers.md
	python -m aurora.experiments.headline

figures:          ## numbers + all slide figures -> figures/slides/
	python -m aurora.run_all

check:            ## fail if a deck number no longer matches the committed results
	python -m aurora.run_all --check

all: test figures
