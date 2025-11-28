.PHONY: setup run test clean

setup:
	@chmod +x setup.sh run.sh
	@./setup.sh

run:
	@./run.sh

test:
	poetry run pytest

clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
