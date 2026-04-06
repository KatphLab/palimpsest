install:
	uv sync --all-groups
	uv run pre-commit install
	uv run pre-commit autoupdate

qa:
	uv run ruff check --fix .
	uv run mypy .
	uv run pytest
