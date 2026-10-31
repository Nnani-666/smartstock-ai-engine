.PHONY: install ingest anomaly segment train evaluate simulate all test lint run

VENV = .venv
PYTHON = PYTHONPATH=. $(VENV)/bin/python
PIP = $(VENV)/bin/pip
PYTEST = $(VENV)/bin/pytest
RUFF = $(VENV)/bin/ruff
UVICORN = $(VENV)/bin/uvicorn

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

ingest:
	$(PYTHON) scripts/01_ingest.py --synthetic

anomaly:
	$(PYTHON) scripts/02_anomaly.py

segment:
	$(PYTHON) scripts/03_segment.py

train:
	$(PYTHON) scripts/04_train_forecast.py

evaluate:
	$(PYTHON) scripts/05_evaluate.py

simulate:
	$(PYTHON) scripts/06_simulate_stockouts.py

all: ingest anomaly segment train evaluate simulate

test:
	$(PYTEST) --cov=app --cov-report=term-missing --cov-fail-under=80

lint:
	$(RUFF) check .

run:
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000
