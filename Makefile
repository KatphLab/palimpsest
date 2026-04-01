install:
	uv sync --all-extras
	uv run pre-commit install
	uv run pre-commit autoupdate
