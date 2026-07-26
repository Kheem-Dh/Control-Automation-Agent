.PHONY: help install data run demo eval stress test api clean all

SEED ?= 42
N ?= 200
CONTROLS ?= AC-1,AC-2,AC-3

help:
	@echo "Targets:"
	@echo "  make install   - pip install -r requirements.txt"
	@echo "  make data      - generate synthetic evidence + ground truth"
	@echo "  make run       - run the agent, write the workpaper"
	@echo "  make eval      - run the eval harness (precision/recall/FPR)"
	@echo "  make stress    - run the stress test (escalation rate)"
	@echo "  make test      - run the pytest suite (rule-only, no API key)"
	@echo "  make demo      - launch the Streamlit demo"
	@echo "  make api       - launch the FastAPI service"
	@echo "  make all       - data + run + eval + stress"

install:
	pip install -r requirements.txt

data:
	python -m ingest.generate --seed $(SEED) --n $(N)

run: data
	python -m agent.run --controls $(CONTROLS)

eval: data
	python -m evals.run

stress: data
	python -m evals.stress

test:
	LLM_PROVIDER=rule python -m pytest

demo:
	streamlit run demo/app.py

api:
	uvicorn api.main:app --reload

all: data run eval stress

clean:
	rm -rf __pycache__ */__pycache__ .pytest_cache
	rm -f evals/stress_results.md
