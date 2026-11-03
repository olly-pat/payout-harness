.PHONY: install test unit drills run

install:
	python -m venv .venv
	.venv/bin/pip install -e ".[test]"

test:
	.venv/bin/python -m pytest

unit:
	.venv/bin/python -m pytest -m unit

drills:
	.venv/bin/python scripts/verify_faults.py

run:
	.venv/bin/uvicorn service.app:create_app --factory --reload
