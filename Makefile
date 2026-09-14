PYTHON ?= python3
export PYTHONPATH := src

.PHONY: help all test validate data dashboard serve clean

help:
	@echo "make test        run the test suite (no dependencies)"
	@echo "make validate    run the data-quality rules over the dataset"
	@echo "make data        regenerate the synthetic dataset"
	@echo "make dashboard   rebuild docs/data/dashboard.json from the dataset"
	@echo "make serve       serve the dashboard at http://localhost:8000"
	@echo "make all         data -> validate -> dashboard"
	@echo "make clean       remove caches and build artefacts"

all: data validate dashboard

test:
	$(PYTHON) -m unittest discover -s tests -v

validate:
	@$(PYTHON) -c "from recruiting_funnel.validate import validate_file, summarise; \
	from recruiting_funnel.dataset import DEFAULT_DATA_PATH, load; \
	rows = load(DEFAULT_DATA_PATH); \
	s = summarise(len(rows), validate_file(DEFAULT_DATA_PATH)); \
	print(f\"rows {s['rows']}  health {s['health']:.2%}  errors {s['errors']}  warnings {s['warnings']}\"); \
	[print(f\"  {r}: {n}\") for r, n in s['by_rule'].items()]; \
	raise SystemExit(1 if s['errors'] else 0)"

data:
	$(PYTHON) -m recruiting_funnel.generate --out data/recruiting_data.csv

dashboard:
	$(PYTHON) -m recruiting_funnel.export --out docs/data/dashboard.json

serve:
	@echo "http://localhost:8000"
	@$(PYTHON) -m http.server 8000 --directory docs

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
